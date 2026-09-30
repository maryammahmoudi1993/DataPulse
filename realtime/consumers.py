from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from realtime.auth import JWT_SUBPROTOCOL
from realtime.publisher import stream_group_name
from streams.models import Stream, Workspace


class StreamConsumer(AsyncJsonWebsocketConsumer):
    """Pushes datapoint and alert events for one stream to a browser."""

    async def connect(self):
        self.stream_id = int(self.scope['url_route']['kwargs']['stream_id'])
        self.group = stream_group_name(self.stream_id)

        if not await self._can_view(self.scope.get('user')):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group, self.channel_name)
        offered = self.scope.get('subprotocols') or []
        await self.accept(subprotocol=JWT_SUBPROTOCOL if JWT_SUBPROTOCOL in offered else None)

    async def disconnect(self, code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def stream_event(self, event):
        """Forward a published event to the client."""
        await self.send_json(event['payload'])

    @database_sync_to_async
    def _can_view(self, user):
        workspaces = Workspace.accessible_to(user)
        return Stream.objects.filter(pk=self.stream_id, workspace__in=workspaces).exists()
