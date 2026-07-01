from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone

def is_staff(user):
    return user.is_staff or user.is_superuser

staff_required = user_passes_test(is_staff, login_url='/')


@login_required
@staff_required
def dashboard(request):
    from apps.ranges.models import RangeDeployment, DeployedVM
    from apps.ranges.models import ActivityLog, RangeTemplate
    from apps.config_server.models import Script
    from apps.users.models import User

    # Stats
    total_users = User.objects.count()
    active_today = User.objects.filter(
        last_seen__date=timezone.now().date()
    ).count()
    active_deployments = RangeDeployment.objects.filter(
        status__in=['running', 'deploying', 'stopped', 'fragmented']
    )
    total_vms_running = DeployedVM.objects.filter(status='running').count()
    total_scripts = Script.objects.count()
    public_scripts = Script.objects.filter(
        visibility__in=['public_view', 'public_edit']
    ).count()
    total_templates = RangeTemplate.objects.count()
    public_templates = RangeTemplate.objects.filter(is_public=True).count()

    # Recent activity
    recent_activity = ActivityLog.objects.select_related('user').all()[:10]

    # All users
    users = User.objects.annotate_with_range_count() if hasattr(
        User.objects, 'annotate_with_range_count'
    ) else User.objects.all()

    context = {
        'total_users': total_users,
        'active_today': active_today,
        'active_deployments': active_deployments,
        'active_deployments_count': active_deployments.count(),
        'total_vms_running': total_vms_running,
        'total_scripts': total_scripts,
        'public_scripts': public_scripts,
        'total_templates': total_templates,
        'public_templates': public_templates,
        'recent_activity': recent_activity,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@staff_required
def all_deployments(request):
    from apps.ranges.models import RangeDeployment
    from django.db.models import Q

    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    user_filter = request.GET.get('user', '')

    deployments = RangeDeployment.objects.select_related(
        'user', 'range_template'
    ).prefetch_related('vms').order_by('-created_at')

    if status_filter:
        deployments = deployments.filter(status=status_filter)
    if user_filter:
        deployments = deployments.filter(user__username=user_filter)
    if search:
        deployments = deployments.filter(
            Q(name__icontains=search) |
            Q(user__username__icontains=search) |
            Q(range_template__name__icontains=search)
        )

    from apps.users.models import User
    users = User.objects.all()

    context = {
        'deployments': deployments,
        'status_filter': status_filter,
        'search': search,
        'user_filter': user_filter,
        'users': users,
    }
    return render(request, 'admin_panel/deployments.html', context)


@login_required
@staff_required
def user_management(request):
    from apps.users.models import User
    from apps.ranges.models import RangeDeployment
    from django.db.models import Count

    users = User.objects.annotate(
        deployment_count=Count('deployments')
    ).order_by('-date_joined')

    context = {'users': users}
    return render(request, 'admin_panel/users.html', context)


@login_required
@staff_required
def activity_log(request):
    from apps.ranges.models import ActivityLog
    from django.db.models import Q

    event_filter = request.GET.get('event', '')
    user_filter = request.GET.get('user', '')
    search = request.GET.get('search', '')

    logs = ActivityLog.objects.select_related('user').all()

    if event_filter:
        logs = logs.filter(event_type=event_filter)
    if user_filter:
        logs = logs.filter(user__username=user_filter)
    if search:
        logs = logs.filter(
            Q(message__icontains=search) |
            Q(user__username__icontains=search)
        )

    logs = logs[:200]

    from apps.users.models import User
    users = User.objects.all()

    context = {
        'logs': logs,
        'event_filter': event_filter,
        'user_filter': user_filter,
        'search': search,
        'users': users,
        'event_types': ActivityLog.EVENT_TYPES,
    }
    return render(request, 'admin_panel/activity.html', context)


@login_required
@staff_required
def force_destroy(request, pk):
    from apps.ranges.models import RangeDeployment
    from apps.proxmox.tasks import teardown_range

    deployment = get_object_or_404(RangeDeployment, pk=pk)
    if request.method == 'POST':
        teardown_range.delay(deployment.pk)
        messages.success(request, f'Destroying {deployment.name}...')
    return redirect('admin_panel_deployments')


@login_required
@staff_required
def force_stop(request, pk):
    from apps.ranges.models import RangeDeployment
    from apps.proxmox.services import stop_vm

    deployment = get_object_or_404(RangeDeployment, pk=pk)
    if request.method == 'POST':
        for vm in deployment.vms.filter(status='running'):
            try:
                stop_vm(deployment.user, vm.node, vm.proxmox_vmid)
                vm.status = 'stopped'
                vm.save()
            except Exception:
                pass
        deployment.status = 'stopped'
        deployment.save()
        messages.success(request, f'{deployment.name} stopped.')
    return redirect('admin_panel_deployments')


@login_required
@staff_required
def toggle_user(request, pk):
    from apps.users.models import User

    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        if user == request.user:
            messages.error(request, "You can't disable your own account.")
            return redirect('admin_panel_users')
        user.is_active = not user.is_active
        user.save()
        status = 'enabled' if user.is_active else 'disabled'
        messages.success(request, f'{user.username} {status}.')
    return redirect('admin_panel_users')

@login_required
@staff_required
def dashboard_stats(request):
    from apps.ranges.models import RangeDeployment, DeployedVM
    from apps.config_server.models import Script
    from apps.ranges.models import RangeTemplate
    from apps.users.models import User

    total_users = User.objects.count()
    active_today = User.objects.filter(
        last_seen__date=timezone.now().date()
    ).count()
    active_deployments_count = RangeDeployment.objects.filter(
        status__in=['running', 'deploying', 'stopped', 'fragmented']
    ).count()
    total_vms_running = DeployedVM.objects.filter(status='running').count()
    total_scripts = Script.objects.count()
    total_templates = RangeTemplate.objects.count()

    return render(request, 'admin_panel/partials/stats.html', {
        'total_users': total_users,
        'active_today': active_today,
        'active_deployments_count': active_deployments_count,
        'total_vms_running': total_vms_running,
        'total_scripts': total_scripts,
        'total_templates': total_templates,
    })


@login_required
@staff_required
def dashboard_deployments(request):
    from apps.ranges.models import RangeDeployment

    active_deployments = RangeDeployment.objects.filter(
        status__in=['running', 'deploying', 'stopped', 'fragmented']
    ).select_related('user', 'range_template').prefetch_related('vms')

    return render(request, 'admin_panel/partials/deployments.html', {
        'active_deployments': active_deployments,
    })


@login_required
@staff_required
def dashboard_activity(request):
    from apps.ranges.models import ActivityLog

    recent_activity = ActivityLog.objects.select_related('user').all()[:10]

    return render(request, 'admin_panel/partials/activity.html', {
        'recent_activity': recent_activity,
    })

@login_required
@staff_required
def deployments_partial(request):
    from apps.ranges.models import RangeDeployment
    from django.db.models import Q

    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    user_filter = request.GET.get('user', '')

    deployments = RangeDeployment.objects.select_related(
        'user', 'range_template'
    ).prefetch_related('vms').order_by('-created_at')

    if status_filter:
        deployments = deployments.filter(status=status_filter)
    if user_filter:
        deployments = deployments.filter(user__username=user_filter)
    if search:
        deployments = deployments.filter(
            Q(name__icontains=search) |
            Q(user__username__icontains=search) |
            Q(range_template__name__icontains=search)
        )

    return render(request, 'admin_panel/partials/deployments_table.html', {
        'deployments': deployments,
    })