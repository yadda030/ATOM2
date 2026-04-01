from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, Http404
from django.utils import timezone
from django.forms import formset_factory
from .models import Script, ScriptVariable, MachineConfig
from .forms import ScriptForm, ScriptVariableForm


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
        is_public=True
    ) | Script.objects.filter(created_by=request.user)

    scripts = scripts.distinct()

    if script_type:
        scripts = scripts.filter(script_type=script_type)
    if search:
        scripts = scripts.filter(name__icontains=search)

    scripts = scripts.prefetch_related('tags', 'variables').order_by('-created_at')

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
    else:
        script = None

    ScriptVariableFormSet = formset_factory(ScriptVariableForm, extra=0, can_delete=True)

    if request.method == 'POST':
        form = ScriptForm(request.POST, instance=script)
        formset = ScriptVariableFormSet(request.POST, prefix='variables')

        if form.is_valid() and formset.is_valid():
            instance = form.save(commit=False)
            if not pk:
                instance.created_by = request.user
            instance.save()
            form.save_m2m()

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

    system_vars = []
    if script:
        system_vars = script.variables.filter(is_system=True)

    context = {
        'form': form,
        'formset': formset,
        'script': script,
        'system_vars': system_vars,
    }
    return render(request, 'config_server/script_edit.html', context)


@login_required
def script_delete(request, pk):
    script = get_object_or_404(Script, pk=pk, created_by=request.user)
    if request.method == 'POST':
        script.delete()
        messages.success(request, 'Script deleted.')
    return redirect('script_list')