from django.urls import re_path
from . import consumers
from apps.inbox.consumers import InboxConsumer
 
websocket_urlpatterns = [
    re_path(r'ws/dashboard/$', consumers.DashboardConsumer.as_asgi()),
    re_path(r'ws/inbox/$', InboxConsumer.as_asgi()),
]