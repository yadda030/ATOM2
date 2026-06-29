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

class VMTemplateNetwork(models.Model):
    """
    A network interface attachment for a VMTemplate.
    Each record represents one NIC on the VM.
    """
    vm_template = models.ForeignKey(VMTemplate, on_delete=models.CASCADE, related_name='network_interfaces')
    network = models.ForeignKey(RangeTemplateNetwork, on_delete=models.SET_NULL, null=True, blank=True)
    interface_index = models.IntegerField(default=0, help_text="NIC index e.g. 0=net0, 1=net1")
    manual_vnet = models.CharField(max_length=255, blank=True, null=True, help_text="Manual vnet if no network selected")
    vlan_tag = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Optional VLAN tag (1–4094)")

    class Meta:
        ordering = ['interface_index']
        unique_together = ('vm_template', 'interface_index')

    def __str__(self):
        return f"{self.vm_template.name} — net{self.interface_index}"

class RangeDeployment(models.Model):
    STATUS_CHOICES = [
        ('undeployed', 'Undeployed'),
        ('pending', 'Pending'),
        ('deploying', 'Deploying'),
        ('running', 'Running'),
        ('stopped', 'Stopped'),
        ('fragmented', 'Fragmented'),
        ('deleting', 'Deleting'),
        ('error', 'Error'),
        ('archived', 'Archived'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deployments')
    range_template = models.ForeignKey(RangeTemplate, on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='undeployed')
    proxmox_pool = models.CharField(max_length=255, blank=True, null=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.status})"

    def get_fragmented(self):
        """Returns True if some VMs are missing or errored."""
        vms = self.vms.all()
        if not vms:
            return False
        return vms.filter(status='error').exists()

    def running_vms(self):
        return self.vms.filter(status='running').count()

    def total_vms(self):
        return self.vms.count()

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
    
class DeployedVMVariable(models.Model):
    """
    Stores per-VM variable values set at deploy time.
    Used by _render_script() to substitute {{ variable }} placeholders.
    """
    deployed_vm = models.ForeignKey(DeployedVM, on_delete=models.CASCADE, related_name='variables')
    key = models.CharField(max_length=255)
    value = models.TextField(blank=True, default='')

    class Meta:
        unique_together = ('deployed_vm', 'key')

    def __str__(self):
        return f"{self.deployed_vm.name} — {self.key} = {self.value}"
    
class ActivityLog(models.Model):
    EVENT_TYPES = [
        ('deployment_started', 'Deployment Started'),
        ('deployment_complete', 'Deployment Complete'),
        ('deployment_stopped', 'Deployment Stopped'),
        ('deployment_failed', 'Deployment Failed'),
        ('vm_checkin', 'VM Checked In'),
        ('vm_failed', 'VM Failed'),
        ('user_registered', 'User Registered'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.event_type} - {self.created_at}"
    
class SiteSettings(models.Model):
    proxmox_vmid_min = models.IntegerField(default=200, help_text="Minimum VMID for training VMs")
    proxmox_vmid_max = models.IntegerField(default=999, help_text="Maximum VMID for training VMs")

    class Meta:
        verbose_name = 'Site settings'
        verbose_name_plural = 'Site settings'

    def __str__(self):
        return f"Site settings (VMID range: {self.proxmox_vmid_min}-{self.proxmox_vmid_max})"

    @classmethod
    def get(cls):
        """Always returns the single settings instance, creating it if needed."""
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings
    
class VMIDLock(models.Model):
    """
    Used to serialize VMID allocation across concurrent deployments.
    Only one record ever exists — it acts as a mutex.
    """
    locked_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'VMID lock'

    @classmethod
    def get(cls):
        lock, _ = cls.objects.get_or_create(pk=1)
        return lock
    
class DeployedVMNIC(models.Model):
    deployed_vm = models.ForeignKey(DeployedVM, on_delete=models.CASCADE, related_name='nics')
    interface_index = models.IntegerField(help_text="NIC index e.g. 0=net0, 1=net1")
    mac_address = models.CharField(max_length=17)

    class Meta:
        ordering = ['interface_index']
        unique_together = ('deployed_vm', 'interface_index')

    def __str__(self):
        return f"{self.deployed_vm.name} — net{self.interface_index} ({self.mac_address})"