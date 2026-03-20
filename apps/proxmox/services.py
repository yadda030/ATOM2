from proxmoxer import ProxmoxAPI


def get_proxmox_connection(user):
    """
    Create a Proxmox API connection using the user's stored credentials.
    """
    if not user.has_proxmox_credentials():
        raise ValueError("User does not have Proxmox credentials configured.")

    proxmox = ProxmoxAPI(
        user.proxmox_host,
        user=user.proxmox_user,
        token_name=user.proxmox_token_name,
        token_value=user.proxmox_token_value,
        verify_ssl=False  # set to True in production with valid certs
    )

    return proxmox


def get_nodes(user):
    """
    Fetch all nodes in the Proxmox cluster.
    """
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes.get()


def get_vms(user, node):
    """
    Fetch all VMs on a specific node.
    """
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).qemu.get()


def get_containers(user, node):
    """
    Fetch all containers on a specific node.
    """
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).lxc.get()


def get_network(user, node):
    """
    Fetch network info for a specific node.
    """
    proxmox = get_proxmox_connection(user)
    return proxmox.nodes(node).network.get()

def get_sdn_zones(user):
    proxmox = get_proxmox_connection(user)
    return proxmox.cluster.sdn.zones.get()

def get_sdn_vnets(user):
    proxmox = get_proxmox_connection(user)
    return proxmox.cluster.sdn.vnets.get()