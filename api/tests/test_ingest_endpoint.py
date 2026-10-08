from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

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
def jwt_client(owner):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(owner).access_token}')
    return api


def _url(stream):
    return f'/api/streams/{stream.id}/ingest/'


def test_ingest_accepts_jwt_auth(jwt_client, stream):
    response = jwt_client.post(_url(stream), {'value': 7}, format='json')

    assert response.status_code == 201
    assert DataPoint.objects.get(pk=response.data['id']).value == 7.0


def test_ingest_accepts_api_key_auth(workspace, owner, stream):
    _, raw_key = APIKey.create(workspace, owner, 'k', [APIKey.SCOPE_WRITE_POINTS])
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Api-Key {raw_key}')

    response = api.post(_url(stream), {'value': '3.5'}, format='json')

    assert response.status_code == 201
    assert response.data['value'] == 3.5


@pytest.mark.parametrize('payload', [
    {'value': 'abc'}, {'value': 'nan'}, {'value': 'inf'}, {}, {'value': 1, 'metadata': 'x'},
])
def test_ingest_non_numeric_value_returns_400(jwt_client, stream, payload):
    response = jwt_client.post(_url(stream), payload, format='json')

    assert response.status_code == 400
    assert not DataPoint.objects.exists()


def test_ingest_dispatches_detection_task(jwt_client, stream):
    with mock.patch('api.views.detect_and_alert') as task:
        response = jwt_client.post(_url(stream), {'value': 1}, format='json')

    task.delay.assert_called_once_with(response.data['id'])


def test_ingest_requires_authentication(stream):
    assert APIClient().post(_url(stream), {'value': 1}, format='json').status_code == 401


def test_ingest_jwt_user_cannot_write_to_foreign_stream(jwt_client):
    other_owner = User.objects.create_user('other', password='x')
    other = Workspace.objects.create(name='O', slug='o', owner=other_owner)
    foreign = Stream.objects.create(workspace=other, name='F', source_type=Stream.SOURCE_SIMULATOR)

    assert jwt_client.post(_url(foreign), {'value': 1}, format='json').status_code == 404
