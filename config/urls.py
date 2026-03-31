from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('config/', include('apps.config_server.urls')),
    path('', include('apps.dashboard.urls')),
    path('accounts/', include('django.contrib.auth.urls')),
]