from django import forms
from .models import Script, ScriptVariable
from apps.ranges.models import Tag


class ScriptForm(forms.ModelForm):
    tags = forms.CharField(required=False, help_text="Comma separated tags")

    class Meta:
        model = Script
        fields = ['name', 'description', 'script_type', 'content', 'visibility']

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


class ScriptVariableForm(forms.ModelForm):
    class Meta:
        model = ScriptVariable
        fields = ['key', 'variable_type', 'default_value', 'description', 'required']