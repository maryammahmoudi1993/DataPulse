import logging
import time

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from realtime.auth import JWT_SUBPROTOCOL, get_user_from_token
from realtime.publisher import stream_group_name
from streams.models import Stream, Workspace

logger = logging.getLogger(__name__)

# Seconds before expiry at which the client is told to refresh its token.
TOKEN_REFRESH_BUFFER = 30
CLOSE_AUTH_FAILED = 4001


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

        # Tell the client when to refresh so the connection never outlives its token.
        if self.scope.get('token_exp'):
            await self.send_json({'type': 'token_ttl', 'seconds': self._seconds_until_refresh()})

    async def disconnect(self, code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        """Handle ``{'type': 'refresh_token', 'access': <JWT>}`` from the client.

        The new token must belong to the user who opened the connection;
        anything else closes the socket. Token values are never logged.
        """
        if not isinstance(content, dict) or content.get('type') != 'refresh_token':
            return

        user, exp = await get_user_from_token(content.get('access', ''))
        current = self.scope.get('user')
        if not user.is_authenticated or not current or user.pk != current.pk:
            await self.send_json({'type': 'auth_error', 'detail': 'Invalid token.'})
            await self.close(code=CLOSE_AUTH_FAILED)
            return

        self.scope['token_exp'] = exp
        await self.send_json({'type': 'token_refreshed', 'seconds': self._seconds_until_refresh()})
        logger.info('WS token refreshed', extra={'stream_id': self.stream_id, 'user_id': user.pk})

    def _seconds_until_refresh(self):
        return max(0, int(self.scope['token_exp'] - time.time()) - TOKEN_REFRESH_BUFFER)

    async def stream_event(self, event):
        """Forward a published event to the client."""
        await self.send_json(event['payload'])

    @database_sync_to_async
    def _can_view(self, user):
        workspaces = Workspace.accessible_to(user)
        return Stream.objects.filter(pk=self.stream_id, workspace__in=workspaces).exists()
