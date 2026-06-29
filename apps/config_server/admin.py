from django.contrib import admin
from .models import Script, ScriptVariable, MachineConfig


class ScriptVariableInline(admin.TabularInline):
    model = ScriptVariable
    extra = 1


@admin.register(Script)
class ScriptAdmin(admin.ModelAdmin):
    list_display = ('name', 'script_type', 'created_by', 'visibility', 'created_at')
    list_filter = ('script_type', 'visibility')
    search_fields = ('name', 'description')
    inlines = [ScriptVariableInline]


@admin.register(MachineConfig)
class MachineConfigAdmin(admin.ModelAdmin):
    list_display = ('mac_address', 'deployed_vm', 'has_checked_in', 'last_checkin')
    list_filter = ('has_checked_in',)
    search_fields = ('mac_address',)