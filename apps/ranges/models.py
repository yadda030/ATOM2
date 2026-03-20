from django.db import models
from django.conf import settings


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class RangeTemplate(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_templates')
    is_public = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, blank=True, related_name='range_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class RangeTemplateNetwork(models.Model):
    range_template = models.ForeignKey(RangeTemplate, on_delete=models.CASCADE, related_name='networks')
    name = models.CharField(max_length=255, help_text="e.g. LAN, WAN, DMZ")
    proxmox_sdn_zone = models.CharField(max_length=255)
    proxmox_sdn_vnet = models.CharField(max_length=255)
    subnet = models.CharField(max_length=255, help_text="e.g. 10.10.1.0/24")
    gateway = models.CharField(max_length=255, help_text="e.g. 10.10.1.1")
    auto_assign_ips = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.range_template.name} - {self.name}"


class VMTemplate(models.Model):
    range_template = models.ForeignKey(RangeTemplate, on_delete=models.CASCADE, related_name='vm_templates')
    name = models.CharField(max_length=255)
    proxmox_template_id = models.IntegerField(help_text="Proxmox template VMID")
    node = models.CharField(max_length=255, help_text="Proxmox node to deploy on")
    cores = models.IntegerField(default=2)
    memory = models.IntegerField(default=2048, help_text="Memory in MB")
    config_script = models.ForeignKey('config_server.Script', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.proxmox_template_id})"


class RangeDeployment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('deploying', 'Deploying'),
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('deleting', 'Deleting'),
        ('error', 'Error'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deployments')
    range_template = models.ForeignKey(RangeTemplate, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.status})"


class RangeNetwork(models.Model):
    deployment = models.ForeignKey(RangeDeployment, on_delete=models.CASCADE, related_name='networks')
    name = models.CharField(max_length=255)
    proxmox_sdn_zone = models.CharField(max_length=255)
    proxmox_sdn_vnet = models.CharField(max_length=255)
    subnet = models.CharField(max_length=255)
    gateway = models.CharField(max_length=255)
    auto_assign_ips = models.BooleanField(default=True)
    copied_from = models.ForeignKey(RangeTemplateNetwork, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.deployment.name} - {self.name}"


class DeployedVM(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('error', 'Error'),
    ]

    deployment = models.ForeignKey(RangeDeployment, on_delete=models.CASCADE, related_name='vms')
    vm_template = models.ForeignKey(VMTemplate, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255)
    proxmox_vmid = models.IntegerField(null=True, blank=True)
    mac_address = models.CharField(max_length=17, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    node = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.proxmox_vmid})"


class DeployedVMConfig(models.Model):
    deployed_vm = models.OneToOneField(DeployedVM, on_delete=models.CASCADE, related_name='config')
    hostname = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    network = models.ForeignKey(RangeNetwork, on_delete=models.SET_NULL, null=True)
    cores = models.IntegerField(null=True, blank=True)
    memory = models.IntegerField(null=True, blank=True, help_text="Memory in MB")
    node = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.deployed_vm.name} config"