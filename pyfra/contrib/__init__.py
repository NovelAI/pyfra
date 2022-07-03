from pyfra import *
from pathlib import Path 
import pyfra.contrib.web as web

@always_rerun()
def tpu_remote(tpu_name, rem_gcp=None, user=None, zone="europe-west4-a", type="v3-8"):
    if rem_gcp:
        machine = rem_gcp

    else:
        machine = local
        
    if user is None:
        user = machine.sh("echo $USER").strip()

    def _get_tpu_ssh():
        ip = machine.sh(f"gcloud alpha compute tpus tpu-vm describe {tpu_name} --format='get(networkEndpoints[0].accessConfig.externalIp)'".strip())
        return Remote(f"{user}@{ip}")
    
    try:
        r = _get_tpu_ssh()
        r.sh("echo hello from tpu")
        return r
    except ShellException:
        pass
    
    tpu_copy_ssh_key(tpu_name, quiet=True)
    return _get_tpu_ssh()

def tpu_vm_sh(pod, cmd, zone="europe-west4-a", executable="bash", quiet=False):
    """
    Run a command in a gcp pod
    """
    if executable == "bash":
        cmd = f"gcloud alpha compute tpus tpu-vm ssh {pod} --zone {zone} --command={quote(cmd)}"
    elif executable == "sh":
        cmd = f"gcloud compute ssh {pod} --command= /bin/sh -c {quote(cmd)}"
    elif executable == None:
        cmd = f"gcloud compute ssh {pod} --command={quote(cmd)}"
    else:
        raise ValueError(f"executable must be bash, sh or None, not {executable}")
    return local.sh(cmd, quiet=quiet)

def tpu_copy_ssh_key(pod: str, key_path: str = None, quiet: bool = False):
    """
    Copy an ssh key to the tpu pod
    """
    if key_path is None:
        for pubkey in (Path(local.home()) / ".ssh").glob("*.pub"):
            tpu_copy_ssh_key(pod, pubkey)
        return
    tpu_vm_sh(
        pod,
        f"echo {quote(local.path(key_path).read().strip())} >> ~/.ssh/authorized_keys",
        quiet=quiet,
    )

def kube_sh(pod, cmd, executable="bash", quiet=False):
    """
    Run a command in a kube pod
    """
    if executable == "bash":
        cmd = f"kubectl exec -it {pod} -- /bin/bash -c {quote(cmd)}"
    elif executable == "sh":
        cmd = f"kubectl exec -it {pod} -- /bin/sh -c {quote(cmd)}"
    elif executable == None:
        cmd = f"kubectl exec -it {pod} -- {quote(cmd)}"
    else:
        raise ValueError(f"executable must be bash, sh or None, not {executable}")
    return local.sh(cmd, quiet=quiet)


def kube_copy_ssh_key(pod: str, key_path: str = None, quiet: bool = False):
    """
    Copy an ssh key to the k8 pod
    """
    if key_path is None:
        for pubkey in (Path(local.home()) / ".ssh").glob("*.pub"):
            kube_copy_ssh_key(pod, pubkey, quiet=quiet)
        return
    kube_sh(
        pod,
        f"echo {quote(local.path(key_path).read().strip())} >> ~/.ssh/authorized_keys",
        quiet=quiet,
    )

def kube_remote(
    pod: str, ssh_key_path: str = None, user=None, service_name=None, local=True, quiet=False
) -> Remote:
    """
    Get a remote object for a k8 pod
    """
    if not local:
        if service_name is None:
            service_name = pod.split("-")[0] + "-service"
        get_ip_cmd = f"kubectl get service/{service_name} -o jsonpath='{{.status.loadBalancer.ingress[0].ip}}'"
        ip = local.sh(get_ip_cmd, quiet=quiet).strip()
    else:
        if service_name:
            ip = service_name
        else:
            ip = pod + "-service"

    if user is not None:
        ip = f"{user}@{ip}"

    # try to connect
    try:
        r = Remote(ip)
        r.sh(f"echo hello from {pod}", quiet=quiet)
        return r
    except ShellException:
        pass

    # copy ssh key
    kube_copy_ssh_key(pod, ssh_key_path, quiet=quiet)

    return Remote(ip)
