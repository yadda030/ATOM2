from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required


def landing(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')


@login_required
def dashboard(request):
    return render(request, 'dashboard/dashboard.html')