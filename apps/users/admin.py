from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User as DefaultUser
from .models import User

# Safely unregister the default User
try:
    admin.site.unregister(DefaultUser)
except admin.sites.NotRegistered:
    pass


class CustomUserAdmin(UserAdmin):
    model = User
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


admin.site.register(User, CustomUserAdmin)