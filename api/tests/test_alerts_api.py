import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from alerts.models import Alert, WebhookEndpoint
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


def test_workspace_members_can_see_streams(stream, workspace):
    member = User.objects.create_user('member', password='x')
    workspace.members.add(member)
    client = APIClient()
    client.force_authenticate(member)

    response = client.get('/api/streams/')

    assert [s['id'] for s in response.data] == [stream.id]


def test_outsider_cannot_see_alerts(stream):
    Alert.objects.create(
        stream=stream, timestamp=timezone.now(), value=1.0, anomaly_score=4.0,
        severity='HIGH', detector_type='ZSCORE',
    )
    client = APIClient()
    client.force_authenticate(User.objects.create_user('outsider', password='x'))

    assert client.get(f'/api/streams/{stream.id}/alerts/').data == []


def test_anonymous_demo_access_disabled_by_default(stream):
    assert APIClient().get('/api/streams/').status_code == 401


def test_anonymous_demo_access_when_enabled(db, settings):
    settings.DEMO_PUBLIC_ACCESS = True
    demo = Workspace.objects.create(name='Demo', slug='demo')
    private = Workspace.objects.create(name='Private', slug='private')
    visible = Stream.objects.create(workspace=demo, name='A', source_type=Stream.SOURCE_SIMULATOR)
    Stream.objects.create(workspace=private, name='B', source_type=Stream.SOURCE_SIMULATOR)

    response = APIClient().get('/api/streams/')

    assert [s['id'] for s in response.data] == [visible.id]


def test_create_webhook(owner, workspace):
    client = APIClient()
    client.force_authenticate(owner)

    response = client.post(
        '/api/webhooks/',
        {'workspace': workspace.id, 'name': 'Ops', 'url': 'https://hooks.example.com/x'},
        format='json',
    )

    assert response.status_code == 201
    assert 'secret' not in response.data
    assert WebhookEndpoint.objects.filter(workspace=workspace).count() == 1
