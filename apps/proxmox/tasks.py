from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.ranges.models import RangeDeployment, DeployedVM
from apps.ranges.models import DeployedVMNIC
from apps.config_server.models import MachineConfig
from . import services
import time
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

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
    try:
        user = User.objects.get(id=user_id)

        if not user.has_proxmox_credentials():
            return "User has no Proxmox credentials"

        deployments = RangeDeployment.objects.filter(
            user=user,
            status__in=['deploying', 'running', 'stopped', 'fragmented']
        )

        channel_layer = get_channel_layer()

        for deployment in deployments:
            for vm in deployment.vms.all():
                if not vm.proxmox_vmid:
                    continue

                previous_status = vm.status

                try:
                    status = services.get_vm_status(user, vm.node, vm.proxmox_vmid)
                    vm.status = _map_proxmox_status(status.get('status'))
                    vm.save()
                except Exception as e:
                    error_msg = str(e)
                    if '500' in error_msg or '404' in error_msg or 'does not exist' in error_msg:
                        vm.status = 'error'
                    else:
                        pass
                    vm.save()

                # Push to browser whenever status changes
                if vm.status != previous_status:
                    try:
                        async_to_sync(channel_layer.group_send)(
                            f'dashboard_{user.id}',
                            {
                                'type': 'vm_status_update',
                                'data': {
                                    'vm_id': vm.id,
                                    'deployment_id': deployment.id,
                                    'status': vm.status,
                                    'status_display': vm.get_status_display(),
                                }
                            }
                        )
                    except Exception:
                        pass

            vm_statuses = set(deployment.vms.values_list('status', flat=True))

            if not vm_statuses:
                continue

            if vm_statuses == {'running'}:
                new_deployment_status = 'running'
            elif vm_statuses == {'stopped'}:
                new_deployment_status = 'stopped'
            else:
                new_deployment_status = 'fragmented'

            if deployment.status != new_deployment_status:
                deployment.status = new_deployment_status
                deployment.save()

                try:
                    async_to_sync(channel_layer.group_send)(
                        f'dashboard_{user.id}',
                        {
                            'type': 'vm_status_update',
                            'data': {
                                'deployment_id': deployment.id,
                                'deployment_status': new_deployment_status,
                                'deployment_status_display': deployment.get_status_display(),
                            }
                        }
                    )
                except Exception:
                    pass

        return f"Polled VMs for user {user.username}"

    except User.DoesNotExist:
        return f"User {user_id} not found"
    except Exception as e:
        return f"Error polling VMs: {str(e)}"


@shared_task
def deploy_range(deployment_id):
    try:
        from apps.ranges.models import RangeDeployment, DeployedVM, ActivityLog, RangeNetwork
        deployment = RangeDeployment.objects.get(id=deployment_id)
        user = deployment.user

        # Validate template resources
        try:
            from apps.proxmox.services import validate_range_template
            warnings = validate_range_template(user, deployment.range_template)
            if warnings:
                deployment.status = 'error'
                deployment.save()
                ActivityLog.objects.create(
                    user=user,
                    event_type='deployment_failed',
                    message=f"Deployment failed validation: {_sanitize_error(', '.join(warnings))}"
                )
                return f"Deployment failed validation: {warnings}"
        except Exception:
            pass

        deployment.status = 'deploying'
        deployment.save()

        # Copy networks from template to deployment
        template_networks = deployment.range_template.networks.all()
        range_network_map = {}  # template network pk → RangeNetwork instance

        for tmpl_net in template_networks:
            range_net = RangeNetwork.objects.create(
                deployment=deployment,
                name=tmpl_net.name,
                proxmox_sdn_zone=tmpl_net.proxmox_sdn_zone,
                proxmox_sdn_vnet=tmpl_net.proxmox_sdn_vnet,
                subnet=tmpl_net.subnet,
                gateway=tmpl_net.gateway,
                auto_assign_ips=tmpl_net.auto_assign_ips,
                copied_from=tmpl_net,
            )
            range_network_map[tmpl_net.pk] = range_net

        vm_templates = deployment.range_template.vm_templates.all()

        for vm_template in vm_templates:
            try:
                # Get next available VMID
                newid = _get_next_vmid(user)

                # Clone the VM
                upid = services.clone_vm(
                    user=user,
                    node=vm_template.node,
                    vmid=vm_template.proxmox_template_id,
                    newid=newid,
                    name=f"{deployment.name}-{vm_template.name}",
                )

                # Wait for clone to complete
                _wait_for_task(user, vm_template.node, upid)

                # Configure network interfaces from VMTemplateNetwork records
                try:
                    network_interfaces = vm_template.network_interfaces.all()
                    if network_interfaces:
                        nic_config = {}
                        for iface in network_interfaces:
                            if iface.network_id and iface.network_id in range_network_map:
                                vnet = range_network_map[iface.network_id].proxmox_sdn_vnet
                            elif iface.network:
                                vnet = iface.network.proxmox_sdn_vnet
                            elif iface.manual_vnet:
                                vnet = iface.manual_vnet
                            else:
                                continue

                            if vnet:
                                nic_key = f'net{iface.interface_index}'
                                if iface.vlan_tag:
                                    nic_config[nic_key] = f'virtio,bridge={vnet},tag={iface.vlan_tag}'
                                else:
                                    nic_config[nic_key] = f'virtio,bridge={vnet}'

                        if nic_config:
                            services.update_vm_config(user, vm_template.node, newid, **nic_config)
                except Exception as e:
                    print(f"Warning: Could not configure network interfaces for {vm_template.name}: {e}")

                # Assign to pool if specified
                if deployment.proxmox_pool:
                    try:
                        proxmox = services.get_proxmox_connection(user)
                        proxmox.pools(deployment.proxmox_pool).put(vms=str(newid))
                    except Exception as e:
                        print(f"Warning: Could not add VM to pool: {e}")

                # Get VM config to capture all MAC addresses
                config = services.get_vm_config(user, vm_template.node, newid)
                all_macs = _extract_all_macs(config)
                primary_mac = all_macs.get(0)

                # Create DeployedVM record
                deployed_vm = DeployedVM.objects.create(
                    deployment=deployment,
                    vm_template=vm_template,
                    name=f"{deployment.name}-{vm_template.name}",
                    proxmox_vmid=newid,
                    mac_address=primary_mac,
                    status='stopped',
                    node=vm_template.node,
                )

                # Store all NIC MACs in DeployedVMNIC records
                for iface_index, mac in all_macs.items():
                    DeployedVMNIC.objects.create(
                        deployed_vm=deployed_vm,
                        interface_index=iface_index,
                        mac_address=mac,
                    )

                # Render and store config script
                if vm_template.config_script:
                    rendered_script = _render_script(
                        deployed_vm=deployed_vm,
                        script=vm_template.config_script,
                    )
                    if primary_mac:
                        MachineConfig.objects.create(
                            deployed_vm=deployed_vm,
                            mac_address=primary_mac,
                            config_script=rendered_script,
                        )

                # Start the VM
                services.start_vm(user, vm_template.node, newid)
                deployed_vm.status = 'running'
                deployed_vm.save()

                ActivityLog.objects.create(
                    user=user,
                    event_type='deployment_complete',
                    message=f"VM '{deployed_vm.name}' deployed successfully (VMID {newid})."
                )

            except Exception as e:
                print(f"Error deploying VM {vm_template.name}: {e}")
                ActivityLog.objects.create(
                    user=user,
                    event_type='deployment_failed',
                    message=f"VM '{vm_template.name}' failed: {_sanitize_error(str(e))}"
                )
                DeployedVM.objects.filter(
                    deployment=deployment,
                    vm_template=vm_template
                ).update(status='error')

        deployment.status = 'running'
        deployment.save()

        ActivityLog.objects.create(
            user=user,
            event_type='deployment_complete',
            message=f"Range '{deployment.name}' deployed successfully."
        )

        return f"Deployment {deployment.name} complete"

    except RangeDeployment.DoesNotExist:
        return f"Deployment {deployment_id} not found"
    except Exception as e:
        try:
            deployment.status = 'error'
            deployment.save()
        except Exception:
            pass
        return f"Error deploying range: {_sanitize_error(str(e))}"


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
                if '500' in error_msg or 'does not exist' in error_msg or '404' in error_msg:
                    print(f"VM {vm.name} already gone from Proxmox — removing database record")
                    vm.delete()
                else:
                    vm.status = 'error'
                    vm.save()

        remaining = deployment.vms.count()
        if remaining == 0:
            deployment.networks.all().delete()
            ActivityLog.objects.create(
                user=user,
                event_type='deployment_stopped',
                message=f"Range '{deployment.name}' destroyed and removed."
            )
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


def _extract_all_macs(config):
    """
    Extract all NIC MAC addresses from Proxmox VM config.
    Returns a dict of {interface_index: mac_address}.
    """
    macs = {}
    for key, value in config.items():
        if key.startswith('net'):
            try:
                index = int(key[3:])
            except ValueError:
                continue
            parts = value.split(',')
            for part in parts:
                if '=' in part:
                    k, v = part.split('=', 1)
                    if k in ('virtio', 'e1000', 'vmxnet3', 'rtl8139'):
                        macs[index] = v.upper()
                        break
    return macs


def _render_script(deployed_vm, script):
    from django.template import Template, Context

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

    for var in deployed_vm.variables.all():
        context_data[var.key] = var.value

    template = Template(script.content)
    context = Context(context_data)
    return template.render(context)


def _sanitize_error(message):
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
    return message[:100] if len(message) > 100 else message