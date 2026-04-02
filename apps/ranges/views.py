from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import RangeTemplate, RangeTemplateNetwork, VMTemplate, Tag
from .forms import RangeTemplateForm, RangeTemplateNetworkForm, VMTemplateForm
from apps.proxmox.services import get_nodes, get_templates, get_sdn_zones, get_sdn_vnets
import json


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

    context = {'templates': templates}
    return render(request, 'ranges/template_list.html', context)


@login_required
def template_edit(request, pk=None):
    if pk:
        template = get_object_or_404(RangeTemplate, pk=pk)
        can_edit = template.created_by == request.user
        if not can_edit:
            messages.error(request, 'You do not have permission to edit this template.')
            return redirect('template_list')
    else:
        template = None
        can_edit = True

    # Fetch Proxmox data for dropdowns
    proxmox_nodes = []
    proxmox_templates = {}
    proxmox_sdn_zones = []
    proxmox_sdn_vnets = []

    user = request.user
    if user.has_proxmox_credentials():
        try:
            nodes = get_nodes(user)
            proxmox_nodes = [n['node'] for n in nodes]
            for node in proxmox_nodes:
                try:
                    proxmox_templates[node] = get_templates(user, node)
                except Exception:
                    proxmox_templates[node] = []
            proxmox_sdn_zones = get_sdn_zones(user)
            proxmox_sdn_vnets = get_sdn_vnets(user)
        except Exception:
            pass

    # Get available scripts for VM template dropdown
    from apps.config_server.models import Script
    scripts = Script.objects.filter(
        created_by=request.user
    ) | Script.objects.filter(
        visibility__in=('public_view', 'public_edit')
    )
    scripts = scripts.distinct()

    if request.method == 'POST':
        form = RangeTemplateForm(request.POST, instance=template)

        if form.is_valid():
            instance = form.save(commit=False)
            if not pk:
                instance.created_by = request.user
            instance.save()
            form.save_m2m()

            # Save networks
            RangeTemplateNetwork.objects.filter(range_template=instance).delete()
            network_data = json.loads(request.POST.get('networks_data', '[]'))
            for net in network_data:
                RangeTemplateNetwork.objects.create(
                    range_template=instance,
                    name=net.get('name', ''),
                    proxmox_sdn_zone=net.get('sdn_zone', ''),
                    proxmox_sdn_vnet=net.get('sdn_vnet', ''),
                    subnet=net.get('subnet', ''),
                    gateway=net.get('gateway', ''),
                    auto_assign_ips=net.get('auto_assign_ips', True),
                )

            # Save VMs
            VMTemplate.objects.filter(range_template=instance).delete()
            vm_data = json.loads(request.POST.get('vms_data', '[]'))
            for vm in vm_data:
                script_id = vm.get('config_script')
                script = None
                if script_id:
                    try:
                        from apps.config_server.models import Script
                        script = Script.objects.get(pk=script_id)
                    except Exception:
                        pass

                VMTemplate.objects.create(
                    range_template=instance,
                    name=vm.get('name', ''),
                    proxmox_template_id=vm.get('proxmox_template_id', 0),
                    node=vm.get('node', ''),
                    cores=vm.get('cores') or 2,
                    memory=vm.get('memory') or 2048,
                    config_script=script,
                    notes=vm.get('notes', ''),
                )

            messages.success(request, 'Range template saved.')
            return redirect('template_list')

    else:
        form = RangeTemplateForm(instance=template)

    networks = []
    vms = []
    if template:
        networks = list(template.networks.values(
            'name', 'proxmox_sdn_zone', 'proxmox_sdn_vnet',
            'subnet', 'gateway', 'auto_assign_ips'
        ))
        vms = list(template.vm_templates.values(
            'name', 'proxmox_template_id', 'node',
            'cores', 'memory', 'config_script_id', 'notes'
        ))

    context = {
        'form': form,
        'template': template,
        'can_edit': can_edit,
        'proxmox_nodes': json.dumps(proxmox_nodes),
        'proxmox_templates': json.dumps(proxmox_templates),
        'proxmox_sdn_zones': json.dumps(proxmox_sdn_zones),
        'proxmox_sdn_vnets': json.dumps(proxmox_sdn_vnets),
        'scripts': scripts,
        'networks_json': json.dumps(networks),
        'vms_json': json.dumps(vms),
    }
    return render(request, 'ranges/template_edit.html', context)


@login_required
def template_delete(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    if request.method == 'POST':
        template.delete()
        messages.success(request, 'Template deleted.')
    return redirect('template_list')