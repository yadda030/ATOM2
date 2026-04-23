from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from encrypted_model_fields.fields import EncryptedCharField
import datetime


class User(AbstractUser):
    proxmox_host = models.CharField(max_length=255, blank=True, null=True, help_text="e.g. https://192.168.1.100:8006")
    proxmox_user = EncryptedCharField(max_length=255, blank=True, null=True, help_text="e.g. root@pam")
    proxmox_token_name = EncryptedCharField(max_length=255, blank=True, null=True, help_text="e.g. mytoken")
    proxmox_token_value = EncryptedCharField(max_length=255, blank=True, null=True, help_text="e.g. xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
    last_seen = models.DateTimeField(null=True, blank=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_set',
        blank=True
    )

    def has_proxmox_credentials(self):
        return all([
            self.proxmox_host,
            self.proxmox_user,
            self.proxmox_token_name,
            self.proxmox_token_value
        ])

    @property
    def is_online(self):
        if not self.last_seen:
            return False
        return timezone.now() - self.last_seen < datetime.timedelta(seconds=30)

    @property
    def presence_display(self):
        if self.is_online:
            return 'Active now'
        if not self.last_seen:
            return 'Never seen'
        diff = timezone.now() - self.last_seen
        minutes = int(diff.total_seconds() / 60)
        if minutes < 60:
            return f'Last seen {minutes}m ago'
        hours = minutes // 60
        if hours < 24:
            return f'Last seen {hours}h ago'
        return f'Last seen {diff.days}d ago'

    def __str__(self):
        return self.username