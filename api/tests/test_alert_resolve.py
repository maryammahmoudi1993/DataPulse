import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from alerts.models import Alert
from audit.models import AuditEvent
from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='x')


@pytest.fixture
def stream(owner):
    workspace = Workspace.objects.create(name='W', slug='w', owner=owner)
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


@pytest.fixture
def alert(stream):
    return Alert.objects.create(
        stream=stream, timestamp=timezone.now(), value=1.0, anomaly_score=4.0,
        severity='HIGH', detector_type='ZSCORE',
    )


@pytest.fixture
def client(owner):
    api_client = APIClient()
    api_client.force_authenticate(owner)
    return api_client


def _url(alert):
    return f'/api/streams/{alert.stream_id}/alerts/{alert.id}/resolve/'


def test_resolve_alert_sets_status_resolved(client, alert):
    response = client.post(_url(alert))

    assert response.status_code == 200
    assert response.data == {'status': Alert.STATUS_RESOLVED}
    alert.refresh_from_db()
    assert alert.status == Alert.STATUS_RESOLVED


def test_resolve_already_resolved_returns_400(client, alert):
    client.post(_url(alert))

    assert client.post(_url(alert)).status_code == 400


def test_resolve_emits_alert_resolved_audit_event(client, alert, owner):
    client.post(_url(alert))

    event = AuditEvent.objects.get(action='ALERT_RESOLVED')
    assert event.actor == owner
    assert event.workspace == alert.stream.workspace
    assert event.metadata == {'alert_id': alert.id}


def test_resolve_requires_authentication(alert):
    assert APIClient().post(_url(alert)).status_code == 401


def test_resolve_hidden_from_non_members(alert):
    outsider = APIClient()
    outsider.force_authenticate(User.objects.create_user('outsider', password='x'))

    assert outsider.post(_url(alert)).status_code == 404
    alert.refresh_from_db()
    assert alert.status == Alert.STATUS_OPEN
