from django.urls import path
from . import views

urlpatterns = [
    path('script/<str:mac_address>/', views.serve_script, name='serve_script'),
]