from django.urls import path
from . import views

urlpatterns = [
    path('templates/', views.template_list, name='template_list'),
    path('templates/new/', views.template_edit, name='template_new'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
]