from django.contrib import admin
from .models import (
    Tag, RangeTemplate, RangeTemplateNetwork,
    VMTemplate, RangeDeployment, RangeNetwork,
    DeployedVM, DeployedVMConfig
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


@admin.register(RangeDeployment)
class RangeDeploymentAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('name', 'user__username')


@admin.register(DeployedVM)
class DeployedVMAdmin(admin.ModelAdmin):
    list_display = ('name', 'deployment', 'status', 'proxmox_vmid', 'mac_address')
    list_filter = ('status',)
    search_fields = ('name', 'mac_address')