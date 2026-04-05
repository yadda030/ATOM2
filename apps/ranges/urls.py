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
]