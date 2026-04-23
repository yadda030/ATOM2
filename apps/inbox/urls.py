from django.urls import path
from . import views

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('new/', views.new_conversation, name='new_conversation'),
    path('<int:pk>/', views.inbox, name='conversation'),
    path('<int:pk>/send/', views.send_message, name='send_message'),
    path('<int:pk>/thread/', views.thread_partial, name='thread_partial'),
]