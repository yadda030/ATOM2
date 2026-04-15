from django.shortcuts import render, redirect
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.proxmox.services import test_connection
from .forms import AccountInfoForm, ProxmoxCredentialsForm


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = UserCreationForm()

    return render(request, 'registration/register.html', {'form': form})


@login_required
def profile(request):
    user = request.user
    connection = test_connection(user)

    account_form = AccountInfoForm(instance=user)
    proxmox_form = ProxmoxCredentialsForm(instance=user)

    if request.method == 'POST':
        if 'save_account' in request.POST:
            account_form = AccountInfoForm(request.POST, instance=user)
            if account_form.is_valid():
                account_form.save()
                messages.success(request, 'Account info updated.')
                return redirect('profile')

        elif 'save_proxmox' in request.POST:
            proxmox_form = ProxmoxCredentialsForm(request.POST, instance=user)
            if proxmox_form.is_valid():
                proxmox_form.save()
                messages.success(request, 'Proxmox credentials updated.')
                return redirect('profile')

    from apps.ranges.models import RangeDeployment
    deployment_count = RangeDeployment.objects.filter(user=user).count()

    context = {
        'account_form': account_form,
        'proxmox_form': proxmox_form,
        'connection': connection,
        'deployment_count': deployment_count,
    }

    return render(request, 'users/profile.html', context)


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully.')
            return redirect('profile')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'users/change_password.html', {'form': form})