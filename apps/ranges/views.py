from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import RangeTemplate, RangeTemplateNetwork, VMTemplate, Tag
from .forms import RangeTemplateForm, RangeTemplateNetworkForm, VMTemplateForm
from apps.proxmox.services import get_nodes, get_templates, get_sdn_zones, get_sdn_vnets
import json


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
    if pk:
        template = get_object_or_404(RangeTemplate, pk=pk)
        if template.created_by != request.user:
            messages.error(request, 'You do not have permission to edit this template.')
            return redirect('template_list')
    else:
        template = None

    if request.method == 'POST':
        form = RangeTemplateForm(request.POST, instance=template)
        if form.is_valid():
            instance = form.save(commit=False)
            if not pk:
                instance.created_by = request.user
            instance.save()
            form.save_m2m()
            return redirect('template_step2', pk=instance.pk)
    else:
        form = RangeTemplateForm(instance=template)

    context = {
        'form': form,
        'template': template,
        'step': 1,
    }
    return render(request, 'ranges/wizard/step1.html', context)


@login_required
def template_step2(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    proxmox_nodes, proxmox_templates, proxmox_sdn_zones, proxmox_sdn_vnets = get_proxmox_data(request.user)

    if request.method == 'POST':
        form = RangeTemplateNetworkForm(request.POST)
        if form.is_valid():
            network = form.save(commit=False)
            network.range_template = template
            network.save()
            messages.success(request, f'Network "{network.name}" saved.')
            return redirect('template_step2', pk=pk)
    else:
        form = RangeTemplateNetworkForm()

    networks = template.networks.all()

    context = {
        'template': template,
        'form': form,
        'networks': networks,
        'step': 2,
        'proxmox_sdn_zones_json': json.dumps(proxmox_sdn_zones),
        'proxmox_sdn_vnets_json': json.dumps(proxmox_sdn_vnets),
    }
    return render(request, 'ranges/wizard/step2.html', context)


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

    if request.method == 'POST':
        form = VMTemplateForm(request.POST)
        if form.is_valid():
            vm = form.save(commit=False)
            vm.range_template = template
            vm.save()
            messages.success(request, f'VM "{vm.name}" saved.')
            return redirect('template_step3', pk=pk)
    else:
        form = VMTemplateForm()

    vms = template.vm_templates.all()
    networks = template.networks.all()

    context = {
        'template': template,
        'form': form,
        'vms': vms,
        'networks': networks,
        'scripts': scripts,
        'step': 3,
        'proxmox_nodes_json': json.dumps(proxmox_nodes),
        'proxmox_templates_json': json.dumps(proxmox_templates),
    }
    return render(request, 'ranges/wizard/step3.html', context)


@login_required
def template_step4(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    networks = template.networks.all()
    vms = template.vm_templates.select_related('config_script').all()

    if request.method == 'POST':
        messages.success(request, f'Template "{template.name}" saved successfully.')
        return redirect('template_list')

    context = {
        'template': template,
        'networks': networks,
        'vms': vms,
        'step': 4,
    }
    return render(request, 'ranges/wizard/step4.html', context)


@login_required
def template_delete(request, pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    if request.method == 'POST':
        template.delete()
        messages.success(request, 'Template deleted.')
    return redirect('template_list')


@login_required
def network_delete(request, pk, network_pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    network = get_object_or_404(RangeTemplateNetwork, pk=network_pk, range_template=template)
    if request.method == 'POST':
        network.delete()
        messages.success(request, 'Network removed.')
    return redirect('template_step2', pk=pk)


@login_required
def vm_template_delete(request, pk, vm_pk):
    template = get_object_or_404(RangeTemplate, pk=pk, created_by=request.user)
    vm = get_object_or_404(VMTemplate, pk=vm_pk, range_template=template)
    if request.method == 'POST':
        vm.delete()
        messages.success(request, 'VM removed.')
    return redirect('template_step3', pk=pk)