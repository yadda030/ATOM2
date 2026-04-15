from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.contrib.auth import get_user_model


# Attach a custom view to the admin site
_original_get_urls = admin.AdminSite.get_urls


def custom_get_urls(self):
    urls = _original_get_urls(self)
    custom = [
        path(
            'cluster-overview/',
            self.admin_view(cluster_overview_view),
            name='cluster_overview',
        ),
    ]
    return custom + urls


admin.AdminSite.get_urls = custom_get_urls


def get_meter_colour(percent):
    if percent > 80:
        return '#a32d2d'
    elif percent > 60:
        return '#a07d10'
    return '#378add'


def cluster_overview_view(request):
    from apps.ranges.models import RangeDeployment, DeployedVM, ActivityLog
    from apps.proxmox.services import get_nodes, get_node_status

    User = get_user_model()

    # --- User stats ---
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    users_with_proxmox = sum(1 for u in User.objects.all() if u.has_proxmox_credentials())

    # --- Deployment stats ---
    deployments = RangeDeployment.objects.filter(is_archived=False)
    total_deployments = deployments.count()
    running_deployments = deployments.filter(status='running').count()
    stopped_deployments = deployments.filter(status='stopped').count()
    error_deployments = deployments.filter(status__in=('error', 'fragmented')).count()

    # --- VM stats ---
    total_vms = DeployedVM.objects.count()
    running_vms = DeployedVM.objects.filter(status='running').count()
    stopped_vms = DeployedVM.objects.filter(status='stopped').count()
    error_vms = DeployedVM.objects.filter(status='error').count()

    # --- Proxmox node stats ---
    nodes_data = []
    proxmox_error = None
    if request.user.has_proxmox_credentials():
        try:
            nodes = get_nodes(request.user)
            for node in nodes:
                try:
                    status = get_node_status(request.user, node['node'])
                    cpu_percent = round(status.get('cpu', 0) * 100, 1)
                    mem_total = status.get('memory', {}).get('total', 0)
                    mem_used = status.get('memory', {}).get('used', 0)
                    mem_percent = round((mem_used / mem_total * 100) if mem_total else 0, 1)
                    nodes_data.append({
                        'name': node['node'],
                        'status': node.get('status', 'unknown'),
                        'cpu_percent': cpu_percent,
                        'mem_used_gb': round(mem_used / 1024 ** 3, 1),
                        'mem_total_gb': round(mem_total / 1024 ** 3, 1),
                        'mem_percent': mem_percent,
                        'cpu_width': cpu_percent,
                        'mem_width': mem_percent,
                        'cpu_colour': get_meter_colour(cpu_percent),
                        'mem_colour': get_meter_colour(mem_percent),
                    })
                except Exception:
                    nodes_data.append({
                        'name': node['node'],
                        'status': 'error',
                        'cpu_percent': 0,
                        'mem_used_gb': 0,
                        'mem_total_gb': 0,
                        'mem_percent': 0,
                        'cpu_width': 0,
                        'mem_width': 0,
                        'cpu_colour': '#888',
                        'mem_colour': '#888',
                    })
        except Exception as e:
            proxmox_error = str(e)
    else:
        proxmox_error = 'No Proxmox credentials configured for your account.'

    # --- Recent activity ---
    recent_activity = ActivityLog.objects.select_related('user').order_by('-created_at')[:20]

    context = {
        **admin.site.each_context(request),
        'title': 'Cluster Overview',
        'total_users': total_users,
        'active_users': active_users,
        'users_with_proxmox': users_with_proxmox,
        'total_deployments': total_deployments,
        'running_deployments': running_deployments,
        'stopped_deployments': stopped_deployments,
        'error_deployments': error_deployments,
        'total_vms': total_vms,
        'running_vms': running_vms,
        'stopped_vms': stopped_vms,
        'error_vms': error_vms,
        'nodes_data': nodes_data,
        'proxmox_error': proxmox_error,
        'recent_activity': recent_activity,
    }
    return render(request, 'admin/cluster_overview.html', context)