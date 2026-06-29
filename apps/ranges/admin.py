from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from .models import (
    Tag, RangeTemplate, RangeTemplateNetwork,
    VMTemplate, RangeDeployment, RangeNetwork,
    DeployedVM, DeployedVMConfig, SiteSettings,
    ActivityLog, DeployedVMNIC, DeployedVMVariable
)


class RangeTemplateNetworkInline(admin.TabularInline):
    model = RangeTemplateNetwork
    extra = 1


class VMTemplateInline(admin.TabularInline):
    model = VMTemplate
    extra = 1


@admin.register(RangeTemplate)
class RangeTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_by', 'is_public', 'created_at')
    list_filter = ('is_public', 'tags')
    search_fields = ('name', 'description')
    inlines = [RangeTemplateNetworkInline, VMTemplateInline]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class DeployedVMInline(admin.TabularInline):
    model = DeployedVM
    fields = ('name', 'node', 'proxmox_vmid', 'status', 'mac_address')
    readonly_fields = ('name', 'node', 'proxmox_vmid', 'status', 'mac_address')
    extra = 0
    can_delete = False


@admin.register(RangeDeployment)
class RangeDeploymentAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'status_badge', 'vm_summary', 'created_at', 'admin_actions')
    list_filter = ('status', 'user')
    search_fields = ('name', 'user__username')
    readonly_fields = ('user', 'range_template', 'created_at', 'updated_at', 'proxmox_pool')
    inlines = [DeployedVMInline]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:deployment_id>/force-stop/',
                self.admin_site.admin_view(self.force_stop_view),
                name='ranges_rangedeployment_force_stop',
            ),
            path(
                '<int:deployment_id>/force-destroy/',
                self.admin_site.admin_view(self.force_destroy_view),
                name='ranges_rangedeployment_force_destroy',
            ),
        ]
        return custom_urls + urls

    def force_stop_view(self, request, deployment_id):
        deployment = RangeDeployment.objects.get(pk=deployment_id)
        try:
            from apps.proxmox.services import stop_vm
            for vm in deployment.vms.filter(status='running'):
                try:
                    stop_vm(deployment.user, vm.node, vm.proxmox_vmid)
                    vm.status = 'stopped'
                    vm.save()
                except Exception:
                    pass
            deployment.status = 'stopped'
            deployment.save()
            self.message_user(request, f'Range "{deployment.name}" force stopped.', messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f'Error stopping range: {str(e)}', messages.ERROR)
        return HttpResponseRedirect(reverse('admin:ranges_rangedeployment_changelist'))

    def force_destroy_view(self, request, deployment_id):
        deployment = RangeDeployment.objects.get(pk=deployment_id)
        try:
            from apps.proxmox.tasks import teardown_range
            teardown_range.delay(deployment.pk)
            self.message_user(request, f'Destroy initiated for "{deployment.name}".', messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f'Error destroying range: {str(e)}', messages.ERROR)
        return HttpResponseRedirect(reverse('admin:ranges_rangedeployment_changelist'))

    def status_badge(self, obj):
        colours = {
            'running':    '#3b6d11',
            'stopped':    '#5c7a96',
            'deploying':  '#a07d10',
            'error':      '#a32d2d',
            'fragmented': '#7a4e00',
            'deleting':   '#a32d2d',
            'archived':   '#888780',
            'pending':    '#5c7a96',
            'undeployed': '#5c7a96',
        }
        colour = colours.get(obj.status, '#5c7a96')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">{}</span>',
            colour, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def vm_summary(self, obj):
        total = obj.total_vms()
        running = obj.running_vms()
        return format_html('<span style="font-size:12px;">{} / {} running</span>', running, total)
    vm_summary.short_description = 'VMs'

    def admin_actions(self, obj):
        if obj.status in ('running', 'stopped', 'fragmented', 'error'):
            stop_url = reverse('admin:ranges_rangedeployment_force_stop', args=[obj.pk])
            destroy_url = reverse('admin:ranges_rangedeployment_force_destroy', args=[obj.pk])
            return format_html(
                '<a href="{}" style="margin-right:8px;color:#a07d10;" '
                'onclick="return confirm(\'Force stop this range?\')">Force Stop</a>'
                '<a href="{}" style="color:#a32d2d;" '
                'onclick="return confirm(\'Destroy all VMs in this range?\')">Force Destroy</a>',
                stop_url, destroy_url
            )
        return '—'
    admin_actions.short_description = 'Actions'


class DeployedVMNICInline(admin.TabularInline):
    model = DeployedVMNIC
    fields = ('interface_index', 'mac_address')
    readonly_fields = ('interface_index', 'mac_address')
    extra = 0
    can_delete = False

@admin.register(DeployedVM)
class DeployedVMAdmin(admin.ModelAdmin):
    list_display = ('name', 'deployment', 'user_link', 'status', 'proxmox_vmid', 'mac_address')
    list_filter = ('status',)
    search_fields = ('name', 'mac_address', 'deployment__user__username')
    inlines = [DeployedVMNICInline]

    def user_link(self, obj):
        return obj.deployment.user.username
    user_link.short_description = 'User'


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ('proxmox_vmid_min', 'proxmox_vmid_max')

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'short_message', 'created_at')
    list_filter = ('event_type', 'user')
    search_fields = ('message', 'user__username')
    readonly_fields = ('event_type', 'user', 'message', 'created_at')
    ordering = ('-created_at',)

    def short_message(self, obj):
        return obj.message[:80] + '...' if len(obj.message) > 80 else obj.message
    short_message.short_description = 'Message'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
@admin.register(DeployedVMVariable)
class DeployedVMVariableAdmin(admin.ModelAdmin):
    list_display = ('deployed_vm', 'key', 'value')
    list_filter = ('deployed_vm__deployment',)
    search_fields = ('key', 'value', 'deployed_vm__name')