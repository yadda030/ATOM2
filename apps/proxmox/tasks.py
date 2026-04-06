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
    try:
        deployment = RangeDeployment.objects.get(id=deployment_id)
        user = deployment.user

        # Validate template resources
        try:
            from apps.proxmox.services import validate_range_template
            warnings = validate_range_template(user, deployment.range_template)
            if warnings:
                deployment.status = 'error'
                deployment.save()
                from apps.ranges.models import ActivityLog
                ActivityLog.objects.create(
                    user=user,
                    event_type='deployment_failed',
                    message=f"Deployment failed validation: {','.join(_sanitize_error(warnings))}"
                )
                return f"Deployment failed validation: {warnings}"
        except Exception as e:
            pass  # if validation itself fails, continue with deployment

        deployment.status = 'deploying'
        deployment.save()

        vm_templates = deployment.range_template.vm_templates.all()

        for vm_template in vm_templates:
            try:
                newid = _get_next_vmid(user)

                upid = services.clone_vm(
                    user=user,
                    node=vm_template.node,
                    vmid=vm_template.proxmox_template_id,
                    newid=newid,
                    name=f"{deployment.name}-{vm_template.name}",
                )

                _wait_for_task(user, vm_template.node, upid)

                config = services.get_vm_config(user, vm_template.node, newid)
                mac_address = _extract_mac(config)

                deployed_vm = DeployedVM.objects.create(
                    deployment=deployment,
                    vm_template=vm_template,
                    name=f"{deployment.name}-{vm_template.name}",
                    proxmox_vmid=newid,
                    mac_address=mac_address,
                    status='stopped',
                    node=vm_template.node,
                )

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
        try:
            deployment.status = 'error'
            deployment.save()
        except Exception:
            pass
        return f"Error deploying range: {str(e)}"


@shared_task
def teardown_range(deployment_id):
    try:
        from apps.ranges.models import RangeDeployment, DeployedVM, ActivityLog
        deployment = RangeDeployment.objects.get(id=deployment_id)
        user = deployment.user

        deployment.status = 'deleting'
        deployment.save()

        vms = deployment.vms.all()
        print(f"Tearing down {deployment.name} — {vms.count()} VMs found")

        for vm in vms:
            print(f"VM: {vm.name} — VMID: {vm.proxmox_vmid} — Status: {vm.status}")
            if not vm.proxmox_vmid:
                vm.delete()
                continue
            try:
                if vm.status == 'running':
                    services.stop_vm(user, vm.node, vm.proxmox_vmid)
                    time.sleep(5)
                services.delete_vm(user, vm.node, vm.proxmox_vmid)
                vm.delete()
                print(f"Deleted {vm.name} successfully")
            except Exception as e:
                error_msg = str(e)
                print(f"Error deleting {vm.name}: {error_msg}")
                # If VM doesn't exist on Proxmox anymore, clean up the database record
                if '500' in error_msg or 'does not exist' in error_msg or '404' in error_msg:
                    print(f"VM {vm.name} already gone from Proxmox — removing database record")
                    vm.delete()
                else:
                    vm.status = 'error'
                    vm.save()

        # Check if all VMs were cleaned up
        # Check if all VMs were cleaned up
        remaining = deployment.vms.count()
        if remaining == 0:
            # Clean up network records
            deployment.networks.all().delete()
            # Log before deleting
            ActivityLog.objects.create(
                user=user,
                event_type='deployment_stopped',
                message=f"Range '{deployment.name}' destroyed and removed."
            )
            # Delete the deployment record entirely
            deployment.delete()
        else:
            deployment.status = 'fragmented'
            deployment.save()
            ActivityLog.objects.create(
                user=user,
                event_type='deployment_failed',
                message=f"Range '{deployment.name}' teardown incomplete — {remaining} VMs could not be removed."
            )

        return f"Teardown of {deployment.name} complete"

    except RangeDeployment.DoesNotExist:
        return f"Deployment {deployment_id} not found"
    except Exception as e:
        try:
            deployment.status = 'error'
            deployment.save()
        except Exception:
            pass
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
    from apps.ranges.models import DeployedVM, SiteSettings, VMIDLock
    from django.db import transaction

    with transaction.atomic():
        # Acquire a database-level lock — only one worker can be here at a time
        VMIDLock.objects.select_for_update().get(pk=1)

        site_settings = SiteSettings.get()
        vmid_min = site_settings.proxmox_vmid_min
        vmid_max = site_settings.proxmox_vmid_max

        proxmox = services.get_proxmox_connection(user)

        cluster_vmids = set()
        try:
            nodes = proxmox.nodes.get()
            for node in nodes:
                try:
                    vms = proxmox.nodes(node['node']).qemu.get()
                    for vm in vms:
                        cluster_vmids.add(vm['vmid'])
                except Exception:
                    pass
                try:
                    containers = proxmox.nodes(node['node']).lxc.get()
                    for ct in containers:
                        cluster_vmids.add(ct['vmid'])
                except Exception:
                    pass
        except Exception as e:
            raise Exception(f"Could not fetch cluster VMIDs: {str(e)}")

        db_vmids = set(
            DeployedVM.objects.filter(
                proxmox_vmid__isnull=False
            ).values_list('proxmox_vmid', flat=True)
        )

        used_vmids = cluster_vmids | db_vmids

        for vmid in range(vmid_min, vmid_max):
            if vmid not in used_vmids:
                return vmid

        raise Exception(
            f"No available VMIDs in range {vmid_min}-{vmid_max}. "
            f"Consider expanding the range in settings."
        )

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

# --- Error Handling ---

def _sanitize_error(message):
    """Strip sensitive connection details from error messages."""
    if 'HTTPSConnectionPool' in message or 'ConnectionError' in message:
        return 'Could not connect to Proxmox cluster.'
    if 'Authentication' in message or '401' in message:
        return 'Proxmox authentication failed. Check your credentials.'
    if '500' in message:
        return 'Proxmox returned an internal server error.'
    if '403' in message:
        return 'Permission denied by Proxmox. Check API token permissions.'
    if 'timeout' in message.lower():
        return 'Connection to Proxmox timed out.'
    # Truncate anything else to 100 chars
    return message[:100] if len(message) > 100 else message