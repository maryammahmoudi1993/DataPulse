from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

JWT_SUBPROTOCOL = 'jwt'


@database_sync_to_async
def _user_from_token(raw_token):
    """Resolve an access token to a user, or AnonymousUser when invalid."""
    try:
        user_id = AccessToken(raw_token)['user_id']
    except (TokenError, KeyError):
        return AnonymousUser()
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    return user or AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Authenticates WebSocket clients that offer ``['jwt', <access token>]``.

    Browsers cannot set headers on a WebSocket, and a token in the URL would
    end up in access logs, so it travels in ``Sec-WebSocket-Protocol``.
    Connections without a token keep the session user set by the wrapped
    auth middleware.
    """

    async def __call__(self, scope, receive, send):
        protocols = list(scope.get('subprotocols') or [])
        if len(protocols) == 2 and protocols[0] == JWT_SUBPROTOCOL:
            scope = dict(scope)
            scope['user'] = await _user_from_token(protocols[1])
        return await super().__call__(scope, receive, send)
