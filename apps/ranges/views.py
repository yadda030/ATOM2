from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import RangeTemplate, RangeTemplateNetwork, VMTemplate, Tag, RangeDeployment, DeployedVM
from .forms import RangeTemplateForm, RangeTemplateNetworkForm, VMTemplateForm
from apps.proxmox.services import get_nodes, get_templates, get_sdn_zones, get_sdn_vnets, get_pools
from apps.proxmox.tasks import deploy_range, teardown_range
import json
from django.db.models import Q

def get_proxmox_data(user):
    proxmox_nodes = []
    proxmox_templates = {}
    proxmox_sdn_zones = []
    proxmox_sdn_vnets = []

    if user.has_proxmox_credentials():
        try:
            nodes = get_nodes(user)
            proxmox_nodes = [n['node'] for n in nodes]
            for node in proxmox_nodes:
                try:
                    proxmox_templates[node] = [
                        {'vmid': t['vmid'], 'name': t.get('name', f"VMID {t['vmid']}")}
                        for t in get_templates(user, node)
                    ]
                except Exception:
                    proxmox_templates[node] = []
            try:
                proxmox_sdn_zones = get_sdn_zones(user)
            except Exception:
                pass
            try:
                proxmox_sdn_vnets = get_sdn_vnets(user)
            except Exception:
                pass
        except Exception:
            pass

    return proxmox_nodes, proxmox_templates, proxmox_sdn_zones, proxmox_sdn_vnets


@login_required
def template_list(request):
    templates = RangeTemplate.objects.filter(
        created_by=request.user
    ) | RangeTemplate.objects.filter(
        is_public=True
    )
    templates = templates.distinct().prefetch_related(
        'tags', 'vm_templates', 'networks'
    ).order_by('-created_at')

    for template in templates:
        template.can_edit = template.created_by == request.user

    return render(request, 'ranges/template_list.html', {'templates': templates})


@login_required
def template_step1(request, pk=None):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user) if pk else None

    if request.method == 'POST':
        form = RangeTemplateForm(request.POST, instance=template)
        if form.is_valid():
            instance = form.save(commit=False)
            if not template:
                instance.created_by = request.user
            instance.save()
            form.save(commit=True)  # this calls our custom save which handles tags
            return redirect('template_step2', pk=instance.pk)
    else:
        form = RangeTemplateForm(instance=template)

    # Build comma separated tags string for the template
    existing_tags = ''
    existing_tags_list = []
    if template:
        existing_tags_list = list(template.tags.values_list('name', flat=True))
        existing_tags = ','.join(existing_tags_list)

    return render(request, 'ranges/wizard/step1.html', {
        'form': form,
        'template': template,
        'existing_tags': existing_tags,
        'existing_tags_list': existing_tags_list,
        'step': 1,
    })


@login_required
def template_view(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk)
 
    if not template.is_public and template.created_by != request.user:
        messages.error(request, 'You do not have permission to view this template.')
        return redirect('template_list')
 
    from .diagram import build_template_diagram
    diagram = None
    try:
        diagram = build_template_diagram(template)
    except Exception:
        pass
 
    return render(request, 'ranges/template_view.html', {
        'template': template,
        'networks': template.networks.all(),
        'vms': template.vm_templates.all(),
        'diagram': diagram,
    })


@login_required
def template_step2(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    proxmox_nodes, proxmox_templates, proxmox_sdn_zones, proxmox_sdn_vnets = get_proxmox_data(request.user)

    return render(request, 'ranges/wizard/step2.html', {
        'template': template,
        'networks': template.networks.all(),
        'proxmox_sdn_zones_json': json.dumps(proxmox_sdn_zones),
        'proxmox_sdn_vnets_json': json.dumps(proxmox_sdn_vnets),
        'step': 2,
        'is_edit': True,
    })


@login_required
def template_step3(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    proxmox_nodes, proxmox_templates, proxmox_sdn_zones, proxmox_sdn_vnets = get_proxmox_data(request.user)

    from apps.config_server.models import Script
    scripts = Script.objects.filter(
        created_by=request.user
    ) | Script.objects.filter(
        visibility__in=('public_view', 'public_edit')
    )
    scripts = scripts.distinct()

    return render(request, 'ranges/wizard/step3.html', {
        'template': template,
        'vms': template.vm_templates.all(),
        'networks': template.networks.all(),
        'scripts': scripts,
        'proxmox_nodes_json': json.dumps(proxmox_nodes),
        'proxmox_templates_json': json.dumps(proxmox_templates),
        'step': 3,
        'is_edit': True,
    })


@login_required
def template_step4(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)

    if request.method == 'POST':
        messages.success(request, 'Range template saved successfully.')
        return redirect('template_list')

    from apps.proxmox.services import validate_range_template
    validation_warnings = validate_range_template(request.user, template)

    return render(request, 'ranges/wizard/step4.html', {
        'template': template,
        'networks': template.networks.all(),
        'vms': template.vm_templates.all(),
        'step': 4,
        'is_edit': True,
        'validation_warnings': validation_warnings,
    })


@login_required
def template_delete(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    if request.method == 'POST':
        template.delete()
        messages.success(request, 'Template deleted.')
    return redirect('template_list')


# --- Network CRUD ---
@login_required
def network_add(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)

    if request.method == 'POST':
        form = RangeTemplateNetworkForm(request.POST)
        if form.is_valid():
            network = form.save(commit=False)
            network.range_template = template
            network.save()
            messages.success(request, 'Network added.')
        else:
            for error in form.errors.values():
                messages.error(request, error)

    return redirect('template_step2', pk=pk)


@login_required
def network_delete(request, pk, net_pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    network = get_object_or_404(RangeTemplateNetwork, pk=net_pk, range_template=template)
    if request.method == 'POST':
        network.delete()
        messages.success(request, 'Network removed.')
    return redirect('template_step2', pk=pk)


# --- VM CRUD ---
@login_required
def vm_add(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)

    if request.method == 'POST':
        form = VMTemplateForm(request.POST)
        if form.is_valid():
            vm = form.save(commit=False)
            vm.range_template = template
            vm.save()

            # Add initial network interface if selected
            network_id = request.POST.get('network')
            if network_id:
                try:
                    from .models import VMTemplateNetwork
                    network = RangeTemplateNetwork.objects.get(pk=network_id)
                    primary_vlan_tag = None
                    try:
                        raw_tag = request.POST.get('primary_vlan_tag', '')
                        if raw_tag:
                            parsed = int(raw_tag)
                            if 1 <= parsed <= 4094:
                                primary_vlan_tag = parsed
                    except (ValueError, TypeError):
                        pass
                    VMTemplateNetwork.objects.create(
                        vm_template=vm,
                        network=network,
                        interface_index=0,
                        vlan_tag=primary_vlan_tag,
                    )
                except RangeTemplateNetwork.DoesNotExist:
                    pass

            messages.success(request, 'VM added.')
        else:
            for error in form.errors.values():
                messages.error(request, error)

    return redirect('template_step3', pk=pk)


@login_required
def vm_delete(request, pk, vm_pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    vm = get_object_or_404(VMTemplate, pk=vm_pk, range_template=template)
    if request.method == 'POST':
        vm.delete()
        messages.success(request, 'VM removed.')
    return redirect('template_step3', pk=pk)

@login_required
def network_edit(request, pk, net_pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    network = get_object_or_404(RangeTemplateNetwork, pk=net_pk, range_template=template)

    if request.method == 'POST':
        form = RangeTemplateNetworkForm(request.POST, instance=network)
        if form.is_valid():
            form.save()
            messages.success(request, 'Network updated.')
        else:
            for error in form.errors.values():
                messages.error(request, error)

    return redirect('template_step2', pk=pk)


@login_required
def vm_edit(request, pk, vm_pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    vm = get_object_or_404(VMTemplate, pk=vm_pk, range_template=template)

    if request.method == 'POST':
        form = VMTemplateForm(request.POST, instance=vm)
        if form.is_valid():
            form.save()
            messages.success(request, 'VM updated.')
        else:
            for error in form.errors.values():
                messages.error(request, error)

    return redirect('template_step3', pk=pk)

@login_required
def vm_network_add(request, pk, vm_pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    vm = get_object_or_404(VMTemplate, pk=vm_pk, range_template=template)

    if request.method == 'POST':
        from .models import VMTemplateNetwork
        networks = request.POST.getlist('network')
        manual_vnets = request.POST.getlist('manual_vnet')
        vlan_tags = request.POST.getlist('vlan_tag')

        # Get current interface count for indexing
        existing_count = vm.network_interfaces.count()

        for i, (network_id, manual_vnet) in enumerate(zip(networks, manual_vnets)):
            network = None
            if network_id:
                try:
                    network = RangeTemplateNetwork.objects.get(pk=network_id)
                except RangeTemplateNetwork.DoesNotExist:
                    pass

            # Skip if both are empty
            if not network and not manual_vnet:
                continue

            # Parse VLAN tag — blank or out-of-range treated as None
            vlan_tag = None
            try:
                raw_tag = vlan_tags[i] if i < len(vlan_tags) else ''
                if raw_tag:
                    parsed = int(raw_tag)
                    if 1 <= parsed <= 4094:
                        vlan_tag = parsed
            except (ValueError, TypeError):
                pass

            VMTemplateNetwork.objects.create(
                vm_template=vm,
                network=network,
                interface_index=existing_count + i,
                manual_vnet=manual_vnet or None,
                vlan_tag=vlan_tag,
            )

        messages.success(request, 'Network interfaces saved.')

    return redirect('template_step3', pk=pk)

@login_required
def vm_network_delete(request, pk, vm_pk, iface_pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    vm = get_object_or_404(VMTemplate, pk=vm_pk, range_template=template)
    from .models import VMTemplateNetwork
    iface = get_object_or_404(VMTemplateNetwork, pk=iface_pk, vm_template=vm)

    if request.method == 'POST':
        iface.delete()
        # Reindex remaining interfaces
        for i, remaining in enumerate(vm.network_interfaces.all()):
            remaining.interface_index = i
            remaining.save()
        messages.success(request, 'Network interface removed.')

    return redirect('template_step3', pk=pk)

@login_required
def range_list(request):
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')

    deployments = RangeDeployment.objects.filter(
        user=request.user
    ).prefetch_related('vms', 'networks', 'range_template__tags')

    if status_filter and status_filter != 'all':
        if status_filter == 'archived':
            deployments = deployments.filter(is_archived=True)
        else:
            deployments = deployments.filter(
                status=status_filter, is_archived=False
            )
    else:
        deployments = deployments.filter(is_archived=False)

    if search:
        deployments = deployments.filter(
            Q(name__icontains=search) |
            Q(range_template__name__icontains=search) |
            Q(range_template__tags__name__icontains=search)
        ).distinct()

    deployments = deployments.order_by('-created_at')

    # Annotate fragmented status
    for deployment in deployments:
        if deployment.get_fragmented():
            deployment.display_status = 'fragmented'
        else:
            deployment.display_status = deployment.status

    context = {
        'deployments': deployments,
        'status_filter': status_filter,
        'search': search,
    }
    return render(request, 'ranges/range_list.html', context)


@login_required
def range_deploy(request):
    templates = RangeTemplate.objects.filter(
        created_by=request.user
    ) | RangeTemplate.objects.filter(is_public=True)
    templates = templates.distinct()

    pools = []
    if request.user.has_proxmox_credentials():
        try:
            pools = get_pools(request.user)
        except Exception:
            pass

    if request.method == 'POST':
        template_id = request.POST.get('template')
        name = request.POST.get('name')
        pool = request.POST.get('pool', '')

        if not template_id or not name:
            messages.error(request, 'Please provide a name and select a template.')
            return redirect('range_deploy')

        template = get_object_or_404(RangeTemplate, pk=template_id)

        deployment = RangeDeployment.objects.create(
            user=request.user,
            range_template=template,
            name=name,
            status='pending',
            proxmox_pool=pool or None,
        )

        # Save per-VM configs from form
        for vm_template in template.vm_templates.all():
            hostname = request.POST.get(f'vm_{vm_template.pk}_hostname', vm_template.name)
            ip_address = request.POST.get(f'vm_{vm_template.pk}_ip_address', '')
            cores = request.POST.get(f'vm_{vm_template.pk}_cores', vm_template.cores)
            memory = request.POST.get(f'vm_{vm_template.pk}_memory', vm_template.memory)
            node = request.POST.get(f'vm_{vm_template.pk}_node', vm_template.node)

            # Create a placeholder DeployedVM to attach config to
            # The real VMID gets set during deploy_range
            deployed_vm = DeployedVM.objects.create(
                deployment=deployment,
                vm_template=vm_template,
                name=f"{name}-{vm_template.name}",
                status='pending',
                node=node,
            )

            # Create DeployedVMConfig
            from apps.ranges.models import DeployedVMConfig
            DeployedVMConfig.objects.create(
                deployed_vm=deployed_vm,
                hostname=hostname,
                ip_address=ip_address or None,
                cores=cores,
                memory=memory,
                node=node,
            )

            # Save custom variables
            if vm_template.config_script:
                from apps.ranges.models import DeployedVMVariable
                for var in vm_template.config_script.variables.filter(is_system=False):
                    value = request.POST.get(f'vm_{vm_template.pk}_var_{var.key}', var.default_value or '')
                    DeployedVMVariable.objects.create(
                        deployed_vm=deployed_vm,
                        key=var.key,
                        value=value,
                    )

        deploy_range.delay(deployment.pk)
        messages.success(request, f'Deploying {name}...')
        return redirect('range_list')

    context = {
        'templates': templates,
        'pools': pools,
    }
    return render(request, 'ranges/range_deploy.html', context)


@login_required
def range_detail(request, pk):
    deployment = get_object_or_404(RangeDeployment, pk=pk, user=request.user)
    vms = deployment.vms.all()

    from .diagram import build_deployment_diagram
    diagram = None
    try:
        diagram = build_deployment_diagram(deployment)
    except Exception as e:
        print(f"DIAGRAM ERROR: {e}")

    context = {
        'deployment': deployment,
        'vms': vms,
        'diagram': diagram,
    }
    return render(request, 'ranges/range_detail.html', context)


@login_required
def range_start(request, pk):
    deployment = get_object_or_404(RangeDeployment, pk=pk, user=request.user)
    if request.method == 'POST':
        from apps.proxmox.services import start_vm
        for vm in deployment.vms.all():
            if vm.proxmox_vmid and vm.status == 'stopped':
                try:
                    start_vm(request.user, vm.node, vm.proxmox_vmid)
                    vm.status = 'running'
                    vm.save()
                except Exception:
                    pass
        deployment.status = 'running'
        deployment.save()
        messages.success(request, f'{deployment.name} started.')
    return redirect('range_detail', pk=pk)


@login_required
def range_stop(request, pk):
    deployment = get_object_or_404(RangeDeployment, pk=pk, user=request.user)
    if request.method == 'POST':
        from apps.proxmox.services import stop_vm
        for vm in deployment.vms.all():
            if vm.proxmox_vmid and vm.status == 'running':
                try:
                    stop_vm(request.user, vm.node, vm.proxmox_vmid)
                    vm.status = 'stopped'
                    vm.save()
                except Exception:
                    pass
        deployment.status = 'stopped'
        deployment.save()
        messages.success(request, f'{deployment.name} stopped.')
    return redirect('range_detail', pk=pk)


@login_required
def range_destroy(request, pk):
    deployment = get_object_or_404(RangeDeployment, pk=pk, user=request.user)
    if request.method == 'POST':
        teardown_range.delay(deployment.pk)
        messages.success(request, f'Destroying {deployment.name}...')
    return redirect('range_list')


@login_required
def range_archive(request, pk):
    deployment = get_object_or_404(RangeDeployment, pk=pk, user=request.user)
    if request.method == 'POST':
        deployment.is_archived = True
        deployment.save()
        messages.success(request, f'{deployment.name} archived.')
    return redirect('range_list')


@login_required
def range_delete(request, pk):
    deployment = get_object_or_404(RangeDeployment, pk=pk, user=request.user)
    if request.method == 'POST':
        deployment.delete()
        messages.success(request, 'Range deleted.')
    return redirect('range_list')


@login_required
def vm_start(request, pk, vm_pk):
    deployment = get_object_or_404(RangeDeployment, pk=pk, user=request.user)
    vm = get_object_or_404(DeployedVM, pk=vm_pk, deployment=deployment)
    if request.method == 'POST':
        from apps.proxmox.services import start_vm
        try:
            start_vm(request.user, vm.node, vm.proxmox_vmid)
            vm.status = 'running'
            vm.save()
            messages.success(request, f'{vm.name} started.')
        except Exception as e:
            messages.error(request, f'Failed to start {vm.name}: {str(e)}')
    return redirect('range_detail', pk=pk)


@login_required
def vm_stop(request, pk, vm_pk):
    deployment = get_object_or_404(RangeDeployment, pk=pk, user=request.user)
    vm = get_object_or_404(DeployedVM, pk=vm_pk, deployment=deployment)
    if request.method == 'POST':
        from apps.proxmox.services import stop_vm
        try:
            stop_vm(request.user, vm.node, vm.proxmox_vmid)
            vm.status = 'stopped'
            vm.save()
            messages.success(request, f'{vm.name} stopped.')
        except Exception as e:
            messages.error(request, f'Failed to stop {vm.name}: {str(e)}')
    return redirect('range_detail', pk=pk)

@login_required
def range_grid(request):
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')

    deployments = RangeDeployment.objects.filter(
        user=request.user
    ).prefetch_related('vms', 'networks', 'range_template__tags')

    if status_filter and status_filter != 'all':
        if status_filter == 'archived':
            deployments = deployments.filter(is_archived=True)
        else:
            deployments = deployments.filter(
                status=status_filter, is_archived=False
            )
    else:
        deployments = deployments.filter(is_archived=False)

    if search:
        deployments = deployments.filter(
            Q(name__icontains=search) |
            Q(range_template__name__icontains=search) |
            Q(range_template__tags__name__icontains=search)
        ).distinct()

    deployments = deployments.order_by('-created_at')

    for deployment in deployments:
        if deployment.get_fragmented():
            deployment.display_status = 'fragmented'
        else:
            deployment.display_status = deployment.status

    return render(request, 'ranges/partials/range_grid.html', {
        'deployments': deployments,
    })

@login_required
def range_detail_partial(request, pk):
    deployment = get_object_or_404(RangeDeployment, pk=pk, user=request.user)
    vms = deployment.vms.all()
    networks = deployment.networks.all()

    from .diagram import build_deployment_diagram
    diagram = None
    try:
        diagram = build_deployment_diagram(deployment)
    except Exception as e:
        print(f"DIAGRAM ERROR: {e}")

    return render(request, 'ranges/partials/range_detail_partial.html', {
        'deployment': deployment,
        'vms': vms,
        'networks': networks,
        'diagram': diagram,
    })

@login_required
def range_header_partial(request, pk):
    deployment = get_object_or_404(RangeDeployment, pk=pk, user=request.user)
    return render(request, 'ranges/partials/range_header_partial.html', {
        'deployment': deployment,
    })