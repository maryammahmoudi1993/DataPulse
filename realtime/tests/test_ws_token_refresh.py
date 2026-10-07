import pytest
from asgiref.sync import async_to_sync
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import AccessToken

from realtime.auth import JWTAuthMiddleware
from realtime.routing import websocket_urlpatterns
from streams.models import Stream, Workspace


@pytest.fixture
def stream(db):
    owner = get_user_model().objects.create_user('owner', password='x')
    workspace = Workspace.objects.create(name='W', slug='w', owner=owner)
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


def _run(stream, steps, token=None):
    """Connect with a JWT, run ``steps(communicator)`` and return its result."""
    token = token or str(AccessToken.for_user(stream.workspace.owner))
    app = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))

    async def scenario():
        communicator = WebsocketCommunicator(app, f'/ws/streams/{stream.id}/', subprotocols=['jwt', token])
        connected, _ = await communicator.connect()
        assert connected
        try:
            return await steps(communicator)
        finally:
            await communicator.disconnect()

    return async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_server_sends_token_ttl_on_connect(stream):
    async def steps(communicator):
        return await communicator.receive_json_from()

    message = _run(stream, steps)

    assert message['type'] == 'token_ttl'
    assert 0 < message['seconds'] <= api_settings.ACCESS_TOKEN_LIFETIME.total_seconds()


@pytest.mark.django_db(transaction=True)
def test_client_can_refresh_token(stream):
    new_token = str(AccessToken.for_user(stream.workspace.owner))

    async def steps(communicator):
        await communicator.receive_json_from()
        await communicator.send_json_to({'type': 'refresh_token', 'access': new_token})
        return await communicator.receive_json_from()

    message = _run(stream, steps)

    assert message['type'] == 'token_refreshed'
    assert message['seconds'] > 0


@pytest.mark.django_db(transaction=True)
def test_invalid_refresh_token_closes_connection(stream):
    async def steps(communicator):
        await communicator.receive_json_from()
        await communicator.send_json_to({'type': 'refresh_token', 'access': 'not-a-token'})
        error = await communicator.receive_json_from()
        closed = await communicator.receive_output()
        return error, closed

    error, closed = _run(stream, steps)

    assert error['type'] == 'auth_error'
    assert closed['type'] == 'websocket.close'
    assert closed['code'] == 4001


@pytest.mark.django_db(transaction=True)
def test_refresh_with_another_users_token_is_rejected(stream):
    stranger = get_user_model().objects.create_user('stranger', password='x')
    foreign_token = str(AccessToken.for_user(stranger))

    async def steps(communicator):
        await communicator.receive_json_from()
        await communicator.send_json_to({'type': 'refresh_token', 'access': foreign_token})
        await communicator.receive_json_from()
        return await communicator.receive_output()

    assert _run(stream, steps)['code'] == 4001
