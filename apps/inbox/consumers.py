import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
import asyncio

class InboxConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = f'inbox_{self.user.id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()
        await self._update_last_seen()

        # Start keepalive ping
        self.keepalive_task = asyncio.ensure_future(self._keepalive())

    async def disconnect(self, close_code):
        # Cancel keepalive
        if hasattr(self, 'keepalive_task'):
            self.keepalive_task.cancel()

        await self._update_last_seen()
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name,
        )

    async def _keepalive(self):
        """Send a ping every 30 seconds to keep the connection alive."""
        while True:
            await asyncio.sleep(30)
            try:
                await self.send(text_data='{"type":"ping"}')
            except Exception:
                break

    async def receive(self, text_data):
        # Ignore pong responses
        pass

    async def new_message(self, event):
        await self._update_last_seen()
        await self.send(text_data=json.dumps(event['data']))

    async def unread_count(self, event):
        await self.send(text_data=json.dumps(event['data']))

    @database_sync_to_async
    def _update_last_seen(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.filter(pk=self.user.pk).update(last_seen=timezone.now())