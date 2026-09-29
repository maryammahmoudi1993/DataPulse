import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(username='maryam', password='testpass123')


@pytest.fixture
def workspace(user):
    return Workspace.objects.create(name='Acme Corp', slug='acme-corp', owner=user)


@pytest.fixture
def api_client():
    return APIClient()


def test_list_streams_requires_auth(api_client):
    response = api_client.get('/api/streams/')

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_stream(api_client, user, workspace):
    api_client.force_authenticate(user=user)

    payload = {
        'workspace': workspace.id,
        'name': 'Temperature Sensor',
        'source_type': Stream.SOURCE_SIMULATOR,
    }
    response = api_client.post('/api/streams/', payload, format='json')

    assert response.status_code == 201
    assert Stream.objects.filter(workspace=workspace, name='Temperature Sensor').exists()


@pytest.mark.django_db
def test_pause_action(api_client, user, workspace):
    stream = Stream.objects.create(
        workspace=workspace,
        name='Sensor',
        source_type=Stream.SOURCE_SIMULATOR,
        status=Stream.STATUS_ACTIVE,
    )
    api_client.force_authenticate(user=user)

    response = api_client.post(f'/api/streams/{stream.id}/pause/')

    stream.refresh_from_db()
    assert response.status_code == 200
    assert stream.status == Stream.STATUS_PAUSED


@pytest.mark.django_db
def test_resume_action(api_client, user, workspace):
    stream = Stream.objects.create(
        workspace=workspace,
        name='Sensor',
        source_type=Stream.SOURCE_SIMULATOR,
        status=Stream.STATUS_PAUSED,
    )
    api_client.force_authenticate(user=user)

    response = api_client.post(f'/api/streams/{stream.id}/resume/')

    stream.refresh_from_db()
    assert response.status_code == 200
    assert stream.status == Stream.STATUS_ACTIVE
