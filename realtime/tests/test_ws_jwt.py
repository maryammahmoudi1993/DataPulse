import pytest
from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from realtime.auth import JWTAuthMiddleware
from realtime.routing import websocket_urlpatterns
from streams.models import Stream, Workspace


@pytest.fixture
def stream(db):
    owner = get_user_model().objects.create_user('owner', password='x')
    workspace = Workspace.objects.create(name='W', slug='w', owner=owner)
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


def _connect(stream, subprotocols):
    app = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))

    async def scenario():
        communicator = WebsocketCommunicator(app, f'/ws/streams/{stream.id}/', subprotocols=subprotocols)
        connected, accepted = await communicator.connect()
        if connected:
            await communicator.disconnect()
        return connected, accepted

    return async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_valid_jwt_subprotocol_is_accepted(stream):
    token = str(AccessToken.for_user(stream.workspace.owner))

    connected, accepted = _connect(stream, ['jwt', token])

    assert connected is True
    assert accepted == 'jwt'


@pytest.mark.django_db(transaction=True)
def test_invalid_jwt_is_rejected(stream):
    connected, _ = _connect(stream, ['jwt', 'not-a-token'])

    assert connected is False


@pytest.mark.django_db(transaction=True)
def test_foreign_user_jwt_is_rejected(stream):
    stranger = get_user_model().objects.create_user('stranger', password='x')
    token = str(AccessToken.for_user(stranger))

    connected, _ = _connect(stream, ['jwt', token])

    assert connected is False
