from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.ranges.models import RangeDeployment, ActivityLog
from apps.proxmox.services import get_nodes, get_node_status
from django.contrib.auth import get_user_model

User = get_user_model()


def landing(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')

from apps.proxmox.services import get_nodes, get_node_status, test_connection

@login_required
def dashboard(request):
    user = request.user

    deployments = RangeDeployment.objects.filter(
        user=user
    ).prefetch_related('vms').order_by('-created_at')

    activity = ActivityLog.objects.filter(
        user=user
    ).order_by('-created_at')[:10]

    # Test Proxmox connection
    connection = test_connection(user)

    cluster_stats = {
        'nodes': [],
        'total_vms': 0,
        'nodes_online': 0,
        'total_nodes': 0,
    }

    if connection['status'] == 'connected':
        try:
            nodes = get_nodes(user)
            for node in nodes:
                try:
                    status = get_node_status(user, node['node'])
                    cluster_stats['nodes'].append({
                        'name': node['node'],
                        'status': node.get('status', 'unknown'),
                        'cpu': round(status.get('cpu', 0) * 100, 1),
                        'memory_used': status.get('memory', {}).get('used', 0),
                        'memory_total': status.get('memory', {}).get('total', 1),
                    })
                    if node.get('status') == 'online':
                        cluster_stats['nodes_online'] += 1
                except Exception:
                    pass

            cluster_stats['total_nodes'] = len(nodes)
            cluster_stats['total_vms'] = sum(
                deployment.vms.filter(status='running').count()
                for deployment in deployments
            )
        except Exception:
            pass

    context = {
        'deployments': deployments,
        'activity': activity,
        'cluster_stats': cluster_stats,
        'connection': connection,
    }

    return render(request, 'dashboard/dashboard.html', context)