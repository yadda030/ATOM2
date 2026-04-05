from django import forms
from .models import RangeTemplate, RangeTemplateNetwork, VMTemplate, Tag


class RangeTemplateForm(forms.ModelForm):
    tags = forms.CharField(required=False)

    class Meta:
        model = RangeTemplate
        fields = ['name', 'description', 'is_public']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['tags'].initial = ','.join(
                self.instance.tags.values_list('name', flat=True)
            )

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            tag_names = [
                t.strip() for t in self.cleaned_data.get('tags', '').split(',')
                if t.strip()
            ]
            tags = []
            for name in tag_names:
                tag, _ = Tag.objects.get_or_create(name=name)
                tags.append(tag)
            instance.tags.set(tags)
        return instance


class RangeTemplateNetworkForm(forms.ModelForm):
    class Meta:
        model = RangeTemplateNetwork
        fields = ['name', 'proxmox_sdn_zone', 'proxmox_sdn_vnet', 'subnet', 'gateway', 'auto_assign_ips']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proxmox_sdn_zone'].required = False
        self.fields['proxmox_sdn_vnet'].required = False
        self.fields['subnet'].required = False
        self.fields['gateway'].required = False


class VMTemplateForm(forms.ModelForm):
    class Meta:
        model = VMTemplate
        fields = ['name', 'proxmox_template_id', 'node', 'cores', 'memory', 'config_script', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cores'].required = False
        self.fields['memory'].required = False
        self.fields['config_script'].required = False
        self.fields['notes'].required = False