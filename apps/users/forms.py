from django import forms
from django.contrib.auth.forms import UserChangeForm, PasswordChangeForm
from .models import User


class AccountInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']


class ProxmoxCredentialsForm(forms.ModelForm):
    proxmox_token_value = forms.CharField(
        widget=forms.PasswordInput(render_value=True),
        required=False
    )

    class Meta:
        model = User
        fields = ['proxmox_host', 'proxmox_user', 'proxmox_token_name', 'proxmox_token_value']