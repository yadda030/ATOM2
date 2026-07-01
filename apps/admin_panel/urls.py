from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='admin_panel_dashboard'),
    path('deployments/', views.all_deployments, name='admin_panel_deployments'),
    path('users/', views.user_management, name='admin_panel_users'),
    path('activity/', views.activity_log, name='admin_panel_activity'),
    path('deployments/<int:pk>/destroy/', views.force_destroy, name='admin_panel_force_destroy'),
    path('deployments/<int:pk>/stop/', views.force_stop, name='admin_panel_force_stop'),
    path('users/<int:pk>/toggle/', views.toggle_user, name='admin_panel_toggle_user'),
    path('partials/stats/', views.dashboard_stats, name='admin_panel_stats'),
    path('partials/deployments/', views.dashboard_deployments, name='admin_panel_deployments_partial'),
    path('partials/activity/', views.dashboard_activity, name='admin_panel_activity_partial'),
    path('deployments/partial/', views.deployments_partial, name='admin_panel_deployments_table'),
]