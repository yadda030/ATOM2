from django.db import models
from django.conf import settings
from apps.ranges.models import Tag, DeployedVM


class Script(models.Model):
    SCRIPT_TYPES = [
        ('bootstrap', 'Bootstrap'),
        ('config', 'Config'),
        ('teardown', 'Teardown'),
    ]

    VISIBILITY_CHOICES = [
        ('private', 'Private'),
        ('public_view', 'Public — view only'),
        ('public_edit', 'Public — editable'),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    script_type = models.CharField(max_length=20, choices=SCRIPT_TYPES, default='config')
    content = models.TextField(help_text="Use {{ variable_name }} for variables")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='private')
    tags = models.ManyToManyField('ranges.Tag', blank=True, related_name='scripts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_editable_by(self, user):
        return self.created_by == user or self.visibility == 'public_edit'

    def is_visible_to(self, user):
        return self.created_by == user or self.visibility in ('public_view', 'public_edit')

    def __str__(self):
        return f"{self.name} ({self.script_type})"


class ScriptVariable(models.Model):
    VARIABLE_TYPES = [
        ('string', 'String'),
        ('integer', 'Integer'),
        ('boolean', 'Boolean'),
        ('ip_address', 'IP Address'),
    ]

    script = models.ForeignKey(Script, on_delete=models.CASCADE, related_name='variables')
    key = models.CharField(max_length=255, help_text="e.g. ip_address, hostname")
    description = models.TextField(blank=True, null=True)
    variable_type = models.CharField(max_length=20, choices=VARIABLE_TYPES, default='string')
    default_value = models.CharField(max_length=255, blank=True, null=True)
    required = models.BooleanField(default=True)
    is_system = models.BooleanField(default=False, help_text="Auto populated from deployment config")

    def __str__(self):
        return f"{self.script.name} - {self.key}"


class MachineConfig(models.Model):
    deployed_vm = models.OneToOneField(DeployedVM, on_delete=models.CASCADE, related_name='machine_config')
    mac_address = models.CharField(max_length=17, unique=True)
    config_script = models.TextField(help_text="Rendered script served to VM on boot")
    has_checked_in = models.BooleanField(default=False)
    last_checkin = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mac_address} - {self.deployed_vm.name}"


class DeployedVMVariable(models.Model):
    deployed_vm = models.ForeignKey(DeployedVM, on_delete=models.CASCADE, related_name='variables')
    script_variable = models.ForeignKey(ScriptVariable, on_delete=models.SET_NULL, null=True, blank=True)
    key = models.CharField(max_length=255)
    value = models.TextField()

    class Meta:
        unique_together = ('deployed_vm', 'key')

    def __str__(self):
        return f"{self.deployed_vm.name} - {self.key}={self.value}"