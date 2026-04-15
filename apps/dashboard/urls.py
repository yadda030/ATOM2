from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/connection-status/', views.connection_status, name='connection_status'),
]