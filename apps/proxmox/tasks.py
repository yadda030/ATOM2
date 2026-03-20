from celery import shared_task
from django.contrib.auth import get_user_model
from .services import get_nodes, get_vms, get_containers, get_network
from .models import ProxmoxSnapshot

User = get_user_model()


@shared_task
def poll_proxmox(user_id):
    """
    Poll Proxmox API for a given user and store the results.
    """
    try:
        user = User.objects.get(id=user_id)

        if not user.has_proxmox_credentials():
            return "User has no Proxmox credentials"

        nodes = get_nodes(user)

        for node in nodes:
            node_name = node['node']
            vms = get_vms(user, node_name)
            containers = get_containers(user, node_name)
            network = get_network(user, node_name)

            ProxmoxSnapshot.objects.create(
                user=user,
                node=node_name,
                node_data=node,
                vms=vms,
                containers=containers,
                network=network,
            )

    except User.DoesNotExist:
        return f"User {user_id} not found"
    except Exception as e:
        return f"Error polling Proxmox: {str(e)}"