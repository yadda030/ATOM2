from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.forms import formset_factory
from .models import Script, ScriptVariable, MachineConfig
from .forms import ScriptForm, ScriptVariableForm
from apps.ranges.models import Tag


def serve_script(request, mac_address):
    try:
        config = MachineConfig.objects.get(mac_address=mac_address)
        config.has_checked_in = True
        config.last_checkin = timezone.now()
        config.save()
        return HttpResponse(config.config_script, content_type='text/plain')
    except MachineConfig.DoesNotExist:
        raise Http404


@login_required
def script_list(request):
    script_type = request.GET.get('type', '')
    search = request.GET.get('search', '')

    scripts = Script.objects.filter(
        created_by=request.user
    ) | Script.objects.filter(
        visibility__in=('public_view', 'public_edit')
    )

    scripts = scripts.distinct()

    if script_type:
        scripts = scripts.filter(script_type=script_type)
    if search:
        scripts = scripts.filter(name__icontains=search)

    scripts = scripts.prefetch_related('tags', 'variables').order_by('-created_at')

    for script in scripts:
        script.can_edit = script.is_editable_by(request.user)

    context = {
        'scripts': scripts,
        'script_type': script_type,
        'search': search,
    }
    return render(request, 'config_server/script_list.html', context)


@login_required
def script_edit(request, pk=None):
    if pk:
        script = get_object_or_404(Script, pk=pk)
        if not script.is_visible_to(request.user):
            messages.error(request, 'You do not have permission to view this script.')
            return redirect('script_list')
        can_edit = script.is_editable_by(request.user)
    else:
        script = None
        can_edit = True

    ScriptVariableFormSet = formset_factory(ScriptVariableForm, extra=0, can_delete=True)

    if request.method == 'POST':
        if not can_edit:
            messages.error(request, 'You do not have permission to edit this script.')
            return redirect('script_list')

        form = ScriptForm(request.POST, instance=script)
        formset = ScriptVariableFormSet(request.POST, prefix='variables')

        if form.is_valid() and formset.is_valid():
            instance = form.save(commit=False)
            if not pk:
                instance.created_by = request.user
            instance.save()

            # Handle tags manually
            tag_names = [t.strip() for t in request.POST.get('tags', '').split(',') if t.strip()]
            tags = []
            for name in tag_names:
                tag, _ = Tag.objects.get_or_create(name=name)
                tags.append(tag)
            instance.tags.set(tags)

            # Save variables
            ScriptVariable.objects.filter(script=instance, is_system=False).delete()
            for var_form in formset:
                if var_form.cleaned_data and not var_form.cleaned_data.get('DELETE'):
                    var = var_form.save(commit=False)
                    var.script = instance
                    var.is_system = False
                    var.save()

            messages.success(request, 'Script saved successfully.')
            return redirect('script_list')
    else:
        form = ScriptForm(instance=script)
        initial = []
        if script:
            initial = list(script.variables.filter(is_system=False).values(
                'key', 'variable_type', 'default_value', 'description', 'required'
            ))
        formset = ScriptVariableFormSet(prefix='variables', initial=initial)

    # Build existing tags for display
    existing_tags = ''
    existing_tags_list = []
    if script:
        existing_tags_list = list(script.tags.values_list('name', flat=True))
        existing_tags = ','.join(existing_tags_list)

    system_vars = []
    if script:
        system_vars = script.variables.filter(is_system=True)

    context = {
        'form': form,
        'formset': formset,
        'script': script,
        'system_vars': system_vars,
        'can_edit': can_edit,
        'existing_tags': existing_tags,
        'existing_tags_list': existing_tags_list,
    }
    return render(request, 'config_server/script_edit.html', context)


@login_required
def script_delete(request, pk):
    script = get_object_or_404(Script, pk=pk)
    if not script.is_editable_by(request.user):
        messages.error(request, 'You do not have permission to delete this script.')
        return redirect('script_list')
    if request.method == 'POST':
        script.delete()
        messages.success(request, 'Script deleted.')
    return redirect('script_list')