from django.urls import path
from . import views

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('new/', views.new_conversation, name='new_conversation'),
    path('<int:pk>/', views.conversation, name='conversation'),
]
