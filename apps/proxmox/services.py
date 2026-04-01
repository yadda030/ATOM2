from proxmoxer import ProxmoxAPI


def get_proxmox_connection(user):
    if not user.has_proxmox_credentials():
        raise ValueError("User does not have Proxmox credentials configured.")

    proxmox = ProxmoxAPI(
        user.proxmox_host,
        user=user.proxmox_user,
        token_name=user.proxmox_token_name,
        token_value=user.proxmox_token_value,
        verify_ssl=False
    )

    return proxmox

def test_connection(user):
    """
    Test if the user's Proxmox credentials are valid.
    Returns a dict with status and message.
    """
    try:
        if not user.has_proxmox_credentials():
            return {'status': 'unconfigured', 'message': 'No credentials configured'}
        
        proxmox = get_proxmox_connection(user)
        proxmox.nodes.get()
        return {'status': 'connected', 'message': 'Connected to Proxmox'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

# --- Nodes ---

def get_nodes(user):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes.get()


def get_node_status(user, node):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).status.get()


# --- VMs ---

def get_vms(user, node):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).qemu.get()


def get_vm_status(user, node, vmid):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).qemu(vmid).status.current.get()


def start_vm(user, node, vmid):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).qemu(vmid).status.start.post()


def stop_vm(user, node, vmid):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).qemu(vmid).status.stop.post()


def clone_vm(user, node, vmid, newid, name, full=True):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).qemu(vmid).clone.post(
        newid=newid,
        name=name,
        full=1 if full else 0
    )


def delete_vm(user, node, vmid):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).qemu(vmid).delete()


def get_vm_config(user, node, vmid):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).qemu(vmid).config.get()


def update_vm_config(user, node, vmid, **kwargs):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).qemu(vmid).config.post(**kwargs)


# --- Containers ---

def get_containers(user, node):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).lxc.get()


def get_container_status(user, node, vmid):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).lxc(vmid).status.current.get()


def start_container(user, node, vmid):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).lxc(vmid).status.start.post()


def stop_container(user, node, vmid):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).lxc(vmid).status.stop.post()


def clone_container(user, node, vmid, newid, name):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).lxc(vmid).clone.post(
        newid=newid,
        name=name,
    )


def delete_container(user, node, vmid):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).lxc(vmid).delete()


# --- Networks ---

def get_network(user, node):
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).network.get()


# --- SDN ---

def get_sdn_zones(user):
    proxmox = get_proxmox_connection(user)
    return proxmox.cluster.sdn.zones.get()


def get_sdn_vnets(user):
    proxmox = get_proxmox_connection(user)
    return proxmox.cluster.sdn.vnets.get()


# --- Templates ---

def get_templates(user, node):
    proxmox = get_proxmox_connection(user)
    vms = proxmox.nodes(node).qemu.get()
    return [vm for vm in vms if vm.get('template') == 1]


# --- Tasks ---

def get_task_status(user, node, upid):
    """
    Check the status of a Proxmox task by its UPID.
    Useful for tracking clone/delete operations.
    """
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).tasks(upid).status.get()