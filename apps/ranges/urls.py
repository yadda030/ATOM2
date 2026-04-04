from django.urls import path
from . import views

urlpatterns = [
    path('templates/', views.template_list, name='template_list'),
    path('templates/new/', views.template_step1, name='template_new'),
    path('templates/<int:pk>/edit/', views.template_step1, name='template_edit'),
    path('templates/<int:pk>/networks/', views.template_step2, name='template_step2'),
    path('templates/<int:pk>/vms/', views.template_step3, name='template_step3'),
    path('templates/<int:pk>/review/', views.template_step4, name='template_step4'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('templates/<int:pk>/networks/<int:network_pk>/delete/', views.network_delete, name='network_delete'),
    path('templates/<int:pk>/vms/<int:vm_pk>/delete/', views.vm_template_delete, name='vm_template_delete'),
]