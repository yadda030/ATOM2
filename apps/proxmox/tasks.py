from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.ranges.models import RangeDeployment, DeployedVM
from apps.config_server.models import MachineConfig
from . import services
import time

User = get_user_model()

@shared_task
def poll_all_users():
    """
    Spawns a poll_user_vms task for every user
    that has Proxmox credentials configured.
    """
    from apps.users.models import User
    users = User.objects.all()
    for user in users:
        if user.has_proxmox_credentials():
            poll_user_vms.delay(user.id)
    return f"Dispatched polling for {users.count()} users"

@shared_task
def poll_user_vms(user_id):
    """
    Poll Proxmox for all deployed VMs belonging to a user
    and update their status in the database.
    """
    try:
        user = User.objects.get(id=user_id)

        if not user.has_proxmox_credentials():
            return "User has no Proxmox credentials"

        # Get all active deployments for this user
        deployments = RangeDeployment.objects.filter(
            user=user,
            status__in=['deploying', 'running', 'stopped']
        )

        for deployment in deployments:
            for vm in deployment.vms.all():
                if not vm.proxmox_vmid:
                    continue

                try:
                    status = services.get_vm_status(user, vm.node, vm.proxmox_vmid)
                    vm.status = _map_proxmox_status(status.get('status'))
                    vm.save()
                except Exception as e:
                    vm.status = 'error'
                    vm.save()

        return f"Polled VMs for user {user.username}"

    except User.DoesNotExist:
        return f"User {user_id} not found"
    except Exception as e:
        return f"Error polling VMs: {str(e)}"


@shared_task
def deploy_range(deployment_id):
    """
    Deploy all VMs in a RangeDeployment.
    Clones each VMTemplate, captures MAC address,
    and creates MachineConfig for config server.
    """
    try:
        deployment = RangeDeployment.objects.get(id=deployment_id)
        user = deployment.user

        deployment.status = 'deploying'
        deployment.save()

        vm_templates = deployment.range_template.vm_templates.all()

        for vm_template in vm_templates:
            try:
                # Get a new VMID
                newid = _get_next_vmid(user)

                # Clone the VM
                upid = services.clone_vm(
                    user=user,
                    node=vm_template.node,
                    vmid=vm_template.proxmox_template_id,
                    newid=newid,
                    name=f"{deployment.name}-{vm_template.name}",
                )

                # Wait for clone task to complete
                _wait_for_task(user, vm_template.node, upid)

                # Get VM config to capture MAC address
                config = services.get_vm_config(user, vm_template.node, newid)
                mac_address = _extract_mac(config)

                # Create DeployedVM record
                deployed_vm = DeployedVM.objects.create(
                    deployment=deployment,
                    vm_template=vm_template,
                    name=f"{deployment.name}-{vm_template.name}",
                    proxmox_vmid=newid,
                    mac_address=mac_address,
                    status='stopped',
                    node=vm_template.node,
                )

                # Render and store config script
                if vm_template.config_script:
                    rendered_script = _render_script(
                        deployed_vm=deployed_vm,
                        script=vm_template.config_script,
                    )
                    MachineConfig.objects.create(
                        deployed_vm=deployed_vm,
                        mac_address=mac_address,
                        config_script=rendered_script,
                    )

                # Start the VM
                services.start_vm(user, vm_template.node, newid)
                deployed_vm.status = 'running'
                deployed_vm.save()

            except Exception as e:
                DeployedVM.objects.filter(
                    deployment=deployment,
                    vm_template=vm_template
                ).update(status='error')

        deployment.status = 'running'
        deployment.save()

        return f"Deployment {deployment.name} complete"

    except RangeDeployment.DoesNotExist:
        return f"Deployment {deployment_id} not found"
    except Exception as e:
        deployment.status = 'error'
        deployment.save()
        return f"Error deploying range: {str(e)}"


@shared_task
def teardown_range(deployment_id):
    """
    Stop and delete all VMs in a RangeDeployment.
    """
    try:
        deployment = RangeDeployment.objects.get(id=deployment_id)
        user = deployment.user

        deployment.status = 'deleting'
        deployment.save()

        for vm in deployment.vms.all():
            if not vm.proxmox_vmid:
                continue
            try:
                # Stop VM first
                services.stop_vm(user, vm.node, vm.proxmox_vmid)
                time.sleep(5)  # give it a moment to stop
                # Delete VM
                services.delete_vm(user, vm.node, vm.proxmox_vmid)
                vm.status = 'stopped'
                vm.save()
            except Exception as e:
                vm.status = 'error'
                vm.save()

        deployment.status = 'stopped'
        deployment.save()

        return f"Teardown of {deployment.name} complete"

    except RangeDeployment.DoesNotExist:
        return f"Deployment {deployment_id} not found"
    except Exception as e:
        deployment.status = 'error'
        deployment.save()
        return f"Error tearing down range: {str(e)}"


# --- Helper functions ---

def _map_proxmox_status(status):
    mapping = {
        'running': 'running',
        'stopped': 'stopped',
        'paused': 'stopped',
    }
    return mapping.get(status, 'error')


def _get_next_vmid(user):
    """
    Ask Proxmox for the next available VMID.
    """
    proxmox = services.get_proxmox_connection(user)
    return proxmox.cluster.nextid.get()


def _wait_for_task(user, node, upid, timeout=300, interval=3):
    """
    Poll a Proxmox task until it completes or times out.
    """
    elapsed = 0
    while elapsed < timeout:
        status = services.get_task_status(user, node, upid)
        if status.get('status') == 'stopped':
            if status.get('exitstatus') == 'OK':
                return True
            else:
                raise Exception(f"Proxmox task failed: {status.get('exitstatus')}")
        time.sleep(interval)
        elapsed += interval
    raise Exception(f"Proxmox task timed out after {timeout}s")


def _extract_mac(config):
    """
    Extract MAC address from Proxmox VM config.
    Proxmox stores network config as 'virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0'
    """
    for key, value in config.items():
        if key.startswith('net'):
            parts = value.split(',')
            for part in parts:
                if '=' in part:
                    k, v = part.split('=', 1)
                    if k in ('virtio', 'e1000', 'vmxnet3', 'rtl8139'):
                        return v.upper()
    return None


def _render_script(deployed_vm, script):
    """
    Render a script by substituting variables with their values.
    System variables are pulled from DeployedVMConfig.
    User defined variables are pulled from DeployedVMVariable.
    """
    from django.template import Template, Context

    # Build context from system variables
    context_data = {}

    try:
        vm_config = deployed_vm.config
        context_data['hostname'] = vm_config.hostname
        context_data['ip_address'] = vm_config.ip_address
        context_data['node'] = vm_config.node
        context_data['cores'] = vm_config.cores
        context_data['memory'] = vm_config.memory
    except Exception:
        pass

    # Add user defined variables
    for var in deployed_vm.variables.all():
        context_data[var.key] = var.value

    template = Template(script.content)
    context = Context(context_data)
    return template.render(context)
