from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from api_keys.models import APIKey
from ingestion.models import DataPoint
from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='x')


@pytest.fixture
def workspace(owner):
    return Workspace.objects.create(name='W', slug='w', owner=owner)


@pytest.fixture
def stream(workspace):
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


@pytest.fixture
def client(owner):
    api = APIClient()
    api.force_authenticate(owner)
    return api


def _key_client(raw_key):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')
    return api


def _make_key(workspace, owner, scopes, **kwargs):
    return APIKey.create(workspace, owner, 'test key', scopes, **kwargs)


def test_create_api_key_returns_raw_key_once(client, workspace):
    response = client.post('/api/api-keys/', {
        'workspace': workspace.id, 'name': 'ci', 'scopes': ['write:datapoints'],
    }, format='json')

    assert response.status_code == 201
    assert response.data['raw_key']
    fetched = client.get(f'/api/api-keys/{response.data["id"]}/')
    assert fetched.status_code == 200
    assert fetched.data['raw_key'] is None
    assert response.data['raw_key'] not in str(fetched.data)


def test_raw_key_has_correct_prefix(client, workspace):
    response = client.post('/api/api-keys/', {'workspace': workspace.id, 'name': 'ci'}, format='json')

    raw_key = response.data['raw_key']
    assert raw_key.startswith('dp_live_')
    stored = APIKey.objects.get(pk=response.data['id'])
    assert stored.prefix == raw_key[:12]
    assert stored.key_hash != raw_key
    assert stored.scopes == ['read:streams']


def test_api_key_authenticates_request(workspace, owner, stream):
    key, raw_key = _make_key(workspace, owner, [APIKey.SCOPE_READ_STREAMS])
    DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=1.0)

    response = _key_client(raw_key).get(f'/api/streams/{stream.id}/datapoints/')

    assert response.status_code == 200
    key.refresh_from_db()
    assert key.last_used is not None


def test_api_key_wrong_hash_returns_401(workspace, owner, stream):
    _, raw_key = _make_key(workspace, owner, [APIKey.SCOPE_READ_STREAMS])
    tampered = raw_key[:-1] + ('0' if raw_key[-1] != '0' else '1')

    response = _key_client(tampered).get(f'/api/streams/{stream.id}/datapoints/')

    assert response.status_code == 401


def test_expired_api_key_returns_401(workspace, owner, stream):
    _, raw_key = _make_key(workspace, owner, [APIKey.SCOPE_READ_STREAMS],
                           expires_at=timezone.now() - timedelta(minutes=1))

    response = _key_client(raw_key).get(f'/api/streams/{stream.id}/datapoints/')

    assert response.status_code == 401


def test_api_key_scope_enforced(workspace, owner, stream):
    _, raw_key = _make_key(workspace, owner, [APIKey.SCOPE_READ_STREAMS])

    response = _key_client(raw_key).post(f'/api/streams/{stream.id}/ingest/', {'value': 1}, format='json')

    assert response.status_code == 403
    assert not DataPoint.objects.exists()


def test_ingest_via_api_key_creates_datapoint(workspace, owner, stream):
    _, raw_key = _make_key(workspace, owner, [APIKey.SCOPE_WRITE_POINTS])

    response = _key_client(raw_key).post(
        f'/api/streams/{stream.id}/ingest/', {'value': 42.5, 'metadata': {'src': 'sensor'}}, format='json',
    )

    assert response.status_code == 201
    point = DataPoint.objects.get(pk=response.data['id'])
    assert (point.stream, point.value, point.metadata) == (stream, 42.5, {'src': 'sensor'})


def test_api_key_rejected_on_endpoints_that_do_not_opt_in(workspace, owner):
    _, raw_key = _make_key(workspace, owner, [APIKey.SCOPE_WRITE_POINTS])

    response = _key_client(raw_key).get('/api/streams/')

    assert response.status_code == 401


def test_api_key_cannot_reach_other_workspace(workspace, owner):
    other_owner = User.objects.create_user('other', password='x')
    other = Workspace.objects.create(name='O', slug='o', owner=other_owner)
    foreign = Stream.objects.create(workspace=other, name='F', source_type=Stream.SOURCE_SIMULATOR)
    _, raw_key = _make_key(workspace, owner, [APIKey.SCOPE_WRITE_POINTS])

    response = _key_client(raw_key).post(f'/api/streams/{foreign.id}/ingest/', {'value': 1}, format='json')

    assert response.status_code == 404


def test_create_rejects_invalid_scope_and_foreign_workspace(client):
    other_owner = User.objects.create_user('other', password='x')
    other = Workspace.objects.create(name='O', slug='o', owner=other_owner)

    bad_scope = client.post('/api/api-keys/', {
        'workspace': other.id, 'name': 'x', 'scopes': ['admin:all'],
    }, format='json')
    foreign = client.post('/api/api-keys/', {'workspace': other.id, 'name': 'x'}, format='json')

    assert bad_scope.status_code == 400
    assert foreign.status_code == 404


def test_delete_api_key_revokes_access(client, workspace, owner, stream):
    key, raw_key = _make_key(workspace, owner, [APIKey.SCOPE_READ_STREAMS])

    assert client.delete(f'/api/api-keys/{key.id}/').status_code == 204

    assert _key_client(raw_key).get(f'/api/streams/{stream.id}/datapoints/').status_code == 401


def test_inactive_api_key_returns_401(workspace, owner, stream):
    key, raw_key = _make_key(workspace, owner, [APIKey.SCOPE_READ_STREAMS])
    key.is_active = False
    key.save(update_fields=['is_active'])

    assert _key_client(raw_key).get(f'/api/streams/{stream.id}/datapoints/').status_code == 401
