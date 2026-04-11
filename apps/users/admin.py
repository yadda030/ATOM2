from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User as DefaultUser
from django.utils.html import format_html
from .models import User

# Safely unregister the default User
try:
    admin.site.unregister(DefaultUser)
except admin.sites.NotRegistered:
    pass


@admin.action(description='Activate selected users')
def activate_users(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    modeladmin.message_user(request, f'{updated} user(s) activated.')


@admin.action(description='Deactivate selected users')
def deactivate_users(modeladmin, request, queryset):
    # Prevent superusers from being deactivated
    queryset = queryset.filter(is_superuser=False)
    updated = queryset.update(is_active=False)
    modeladmin.message_user(request, f'{updated} user(s) deactivated.')


class CustomUserAdmin(UserAdmin):
    model = User
    actions = [activate_users, deactivate_users]
    list_display = ('username', 'email', 'full_name', 'is_active', 'proxmox_status', 'deployment_count', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'first_name', 'last_name')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Proxmox Credentials', {
            'fields': (
                'proxmox_host',
                'proxmox_user',
                'proxmox_token_name',
                'proxmox_token_value',
            )
        }),
        ('Permissions', {
            'fields': (
                'is_active',
                'is_staff',
                'is_superuser',
                'groups',
                'user_permissions',
            )
        }),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('Proxmox Credentials', {
            'fields': (
                'proxmox_host',
                'proxmox_user',
                'proxmox_token_name',
                'proxmox_token_value',
            )
        }),
    )

    def full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip() or '—'
    full_name.short_description = 'Name'

    def proxmox_status(self, obj):
        if obj.has_proxmox_credentials():
            return format_html(
                '<span style="color:#3b6d11;font-weight:500;">&#10003; Configured</span>'
            )
        return format_html('<span style="color:#8a9bb0;">Not configured</span>')
    proxmox_status.short_description = 'Proxmox'

    def deployment_count(self, obj):
        count = obj.deployments.filter(is_archived=False).count()
        return count
    deployment_count.short_description = 'Deployments'


admin.site.register(User, CustomUserAdmin)