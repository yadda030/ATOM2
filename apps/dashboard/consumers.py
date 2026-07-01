import asyncio
import json
from channels.generic.websocket import AsyncWebsocketConsumer


class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close()
            return

        self.group_name = f'dashboard_{self.user.id}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()
        self.keepalive_task = asyncio.ensure_future(self._keepalive())

    async def disconnect(self, close_code):
        if hasattr(self, 'keepalive_task'):
            self.keepalive_task.cancel()
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        pass

    async def _keepalive(self):
        while True:
            await asyncio.sleep(30)
            try:
                await self.send(text_data='{"type":"ping"}')
            except Exception:
                break

    async def vm_status_update(self, event):
        await self.send(text_data=json.dumps(event['data']))