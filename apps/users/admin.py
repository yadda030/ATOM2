from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    model = User
    fieldsets = UserAdmin.fieldsets + (
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