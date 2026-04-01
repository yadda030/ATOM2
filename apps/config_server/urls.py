from django.urls import path
from . import views

urlpatterns = [
    path('script/<str:mac_address>/', views.serve_script, name='serve_script'),
    path('scripts/', views.script_list, name='script_list'),
    path('scripts/new/', views.script_edit, name='script_new'),
    path('scripts/<int:pk>/edit/', views.script_edit, name='script_edit'),
    path('scripts/<int:pk>/delete/', views.script_delete, name='script_delete'),
]