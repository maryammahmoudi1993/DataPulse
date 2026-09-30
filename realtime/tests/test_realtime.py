import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from realtime.publisher import publish_stream_event, stream_group_name
from realtime.routing import websocket_urlpatterns
from streams.models import Stream, Workspace


@pytest.fixture
def stream(db):
    owner = get_user_model().objects.create_user('owner', password='x')
    workspace = Workspace.objects.create(name='W', slug='w', owner=owner)
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


def _communicator(stream, user=None):
    communicator = WebsocketCommunicator(URLRouter(websocket_urlpatterns), f'/ws/streams/{stream.id}/')
    communicator.scope['user'] = user or AnonymousUser()
    return communicator


def test_publish_reaches_group_subscribers():
    layer = get_channel_layer()

    async def scenario():
        channel = await layer.new_channel()
        await layer.group_add(stream_group_name(7), channel)
        return channel

    channel = async_to_sync(scenario)()

    assert publish_stream_event(7, {'type': 'datapoint'}) is True
    message = async_to_sync(layer.receive)(channel)
    assert message['payload']['type'] == 'datapoint'


@pytest.mark.django_db(transaction=True)
def test_consumer_rejects_anonymous(stream):
    async def scenario():
        connected, _ = await _communicator(stream).connect()
        return connected

    assert async_to_sync(scenario)() is False


@pytest.mark.django_db(transaction=True)
def test_consumer_streams_events_to_owner(stream):
    async def scenario():
        communicator = _communicator(stream, user=stream.workspace.owner)
        connected, _ = await communicator.connect()
        assert connected
        await get_channel_layer().group_send(
            stream_group_name(stream.id),
            {'type': 'stream.event', 'payload': {'type': 'alert', 'alert_id': 1}},
        )
        message = await communicator.receive_json_from()
        await communicator.disconnect()
        return message

    assert async_to_sync(scenario)()['alert_id'] == 1
