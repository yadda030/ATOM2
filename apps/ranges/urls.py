from django.urls import path
from . import views

urlpatterns = [
    path('templates/', views.template_list, name='template_list'),
    path('templates/new/', views.template_step1, name='template_new'),
    path('templates/<int:pk>/edit/', views.template_step1, name='template_edit'),
    path('templates/<int:pk>/step2/', views.template_step2, name='template_step2'),
    path('templates/<int:pk>/step3/', views.template_step3, name='template_step3'),
    path('templates/<int:pk>/step4/', views.template_step4, name='template_step4'),
    path('templates/<int:pk>/view/', views.template_view, name='template_view'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    # Network CRUD
    path('templates/<int:pk>/networks/add/', views.network_add, name='network_add'),
    path('templates/<int:pk>/networks/<int:net_pk>/edit/', views.network_edit, name='network_edit'),
    path('templates/<int:pk>/networks/<int:net_pk>/delete/', views.network_delete, name='network_delete'),
    # VM CRUD
    path('templates/<int:pk>/vms/add/', views.vm_add, name='vm_add'),
    path('templates/<int:pk>/vms/<int:vm_pk>/edit/', views.vm_edit, name='vm_edit'),
    path('templates/<int:pk>/vms/<int:vm_pk>/delete/', views.vm_delete, name='vm_delete'),

    # Range deployment URLs
    path('', views.range_list, name='range_list'),
    path('deploy/', views.range_deploy, name='range_deploy'),
    path('<int:pk>/', views.range_detail, name='range_detail'),
    path('<int:pk>/start/', views.range_start, name='range_start'),
    path('<int:pk>/stop/', views.range_stop, name='range_stop'),
    path('<int:pk>/destroy/', views.range_destroy, name='range_destroy'),
    path('<int:pk>/archive/', views.range_archive, name='range_archive'),
    path('<int:pk>/delete/', views.range_delete, name='range_delete'),
    path('<int:pk>/vms/<int:vm_pk>/start/', views.vm_start, name='vm_start'),
    path('<int:pk>/vms/<int:vm_pk>/stop/', views.vm_stop, name='vm_stop'),

    path('grid/', views.range_grid, name='range_grid'),
]