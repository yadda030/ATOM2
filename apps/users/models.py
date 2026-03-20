from django.contrib.auth.models import AbstractUser
from django.db import models
from encrypted_model_fields.fields import EncryptedCharField


class User(AbstractUser):
    proxmox_host = models.CharField(max_length=255, blank=True, null=True, help_text="e.g. https://192.168.1.100:8006")
    proxmox_user = EncryptedCharField(max_length=255, blank=True, null=True, help_text="e.g. root@pam")
    proxmox_token_name = EncryptedCharField(max_length=255, blank=True, null=True, help_text="e.g. mytoken")
    proxmox_token_value = EncryptedCharField(max_length=255, blank=True, null=True, help_text="e.g. xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

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

    def __str__(self):
        return self.username