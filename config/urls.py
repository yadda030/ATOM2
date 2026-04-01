from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('config/', include('apps.config_server.urls')),
    path('', include('apps.dashboard.urls')),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='landing.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/', include('apps.users.urls')),
]