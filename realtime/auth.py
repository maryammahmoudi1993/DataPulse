from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

JWT_SUBPROTOCOL = 'jwt'


@database_sync_to_async
def get_user_from_token(raw_token):
    """Resolve an access token to ``(user, exp)``.

    Returns:
        The active user and the token's expiry as a Unix timestamp, or
        ``(AnonymousUser, None)`` when the token is invalid or expired.
    """
    try:
        token = AccessToken(raw_token)
        user_id = token['user_id']
        exp = int(token['exp'])
    except (TokenError, KeyError):
        return AnonymousUser(), None
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return AnonymousUser(), None
    return user, exp


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
            scope['user'], scope['token_exp'] = await get_user_from_token(protocols[1])
        return await super().__call__(scope, receive, send)
