from django.urls import re_path

from realtime.consumers import StreamConsumer

websocket_urlpatterns = [
    re_path(r'^ws/streams/(?P<stream_id>\d+)/$', StreamConsumer.as_asgi()),
]
