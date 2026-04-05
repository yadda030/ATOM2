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

# --- Pools ---

def get_pools(user):
    proxmox = get_proxmox_connection(user)
    return proxmox.pools.get()

def create_pool(user, pool_id, comment=''):
    proxmox = get_proxmox_connection(user)
    return proxmox.pools.post(poolid=pool_id, comment=comment)

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

# --- Validation Checks ---

def validate_range_template(user, template):
    """
    Validates that all Proxmox resources referenced in a
    RangeTemplate still exist. Returns a list of warnings.
    """
    warnings = []

    if not user.has_proxmox_credentials():
        return ['No Proxmox credentials configured.']

    try:
        nodes = get_nodes(user)
        node_names = [n['node'] for n in nodes]
        online_nodes = [n['node'] for n in nodes if n.get('status') == 'online']

        for vm in template.vm_templates.all():
            # Check node exists
            if vm.node not in node_names:
                warnings.append(f"VM '{vm.name}': node '{vm.node}' not found in cluster.")
                continue

            # Check node is online
            if vm.node not in online_nodes:
                warnings.append(f"VM '{vm.name}': node '{vm.node}' is offline.")
                continue

            # Check template VMID exists
            try:
                templates = get_templates(user, vm.node)
                vmids = [t['vmid'] for t in templates]
                if vm.proxmox_template_id not in vmids:
                    warnings.append(f"VM '{vm.name}': template VMID {vm.proxmox_template_id} not found on '{vm.node}'.")
            except Exception:
                warnings.append(f"VM '{vm.name}': could not verify template VMID {vm.proxmox_template_id}.")

        # Check networks
        try:
            sdn_vnets = [v['vnet'] for v in get_sdn_vnets(user)]
            for network in template.networks.all():
                if network.proxmox_sdn_vnet and network.proxmox_sdn_vnet not in sdn_vnets:
                    warnings.append(f"Network '{network.name}': VNet '{network.proxmox_sdn_vnet}' not found in cluster.")
        except Exception:
            pass

    except Exception as e:
        warnings.append(f"Could not connect to Proxmox: {str(e)}")

    return warnings