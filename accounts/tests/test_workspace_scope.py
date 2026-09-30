import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import UserWorkspace
from streams.models import Stream, Workspace

User = get_user_model()


def _register(client, username, slug):
    tokens = client.post(
        '/api/auth/register/',
        {'username': username, 'password': 'S3cure-pass!', 'workspace': slug},
        format='json',
    ).data
    return tokens['access']


def _authed(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    return client


@pytest.fixture
def two_tenants(db):
    anon = APIClient()
    token_a = _register(anon, 'alice', 'alpha')
    token_b = _register(anon, 'bob', 'beta')
    Stream.objects.create(
        workspace=Workspace.objects.get(slug='beta'), name='Bobs stream', source_type=Stream.SOURCE_SIMULATOR,
    )
    return token_a, token_b


def test_stream_isolated_between_workspaces(two_tenants):
    token_a, token_b = two_tenants
    stream = Stream.objects.get(name='Bobs stream')

    listing = _authed(token_a).get('/api/streams/')
    detail = _authed(token_a).get(f'/api/streams/{stream.id}/')

    assert listing.status_code == 200
    assert listing.data == []
    assert detail.status_code == 404
    assert _authed(token_b).get(f'/api/streams/{stream.id}/').status_code == 200


def test_stream_visible_to_workspace_member(two_tenants):
    _, token_b = two_tenants
    carol = User.objects.create_user('carol', password='S3cure-pass!')
    UserWorkspace.objects.create(
        user=carol, workspace=Workspace.objects.get(slug='beta'), role=UserWorkspace.ROLE_MEMBER,
    )
    access = APIClient().post(
        '/api/auth/token/', {'username': 'carol', 'password': 'S3cure-pass!'}, format='json',
    ).data['access']

    response = _authed(access).get('/api/streams/')

    assert response.status_code == 200
    assert [s['name'] for s in response.data] == ['Bobs stream']


def test_create_stream_assigns_to_user_workspace(two_tenants):
    token_a, _ = two_tenants
    alpha = Workspace.objects.get(slug='alpha')
    beta = Workspace.objects.get(slug='beta')
    client = _authed(token_a)
    payload = {'name': 'Mine', 'source_type': Stream.SOURCE_SIMULATOR}

    ok = client.post('/api/streams/', {**payload, 'workspace': alpha.id}, format='json')
    foreign = client.post('/api/streams/', {**payload, 'workspace': beta.id}, format='json')

    assert ok.status_code == 201
    assert Stream.objects.get(pk=ok.data['id']).workspace == alpha
    assert foreign.status_code == 404
    assert not Stream.objects.filter(workspace=beta, name='Mine').exists()
