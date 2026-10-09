"""ASGI config for datapulse.

Routes HTTP to Django and WebSocket traffic to the realtime consumers.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datapulse.settings')

django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack  # noqa: E402
from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from django.urls import path  # noqa: E402

from graphql_api.views import ws_consumer  # noqa: E402
from realtime.auth import JWTAuthMiddleware  # noqa: E402
from realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AuthMiddlewareStack(JWTAuthMiddleware(URLRouter([path('graphql/', ws_consumer())] + websocket_urlpatterns))),
})
