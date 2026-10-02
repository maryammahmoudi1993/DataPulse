import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import UserWorkspace
from alerts.models import Alert, WebhookEndpoint
from audit.models import AuditEvent
from audit.services import get_client_ip, log_event
from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='x')


@pytest.fixture
def workspace(owner):
    ws = Workspace.objects.create(name='W', slug='w', owner=owner)
    UserWorkspace.objects.create(user=owner, workspace=ws, role=UserWorkspace.ROLE_OWNER)
    return ws


@pytest.fixture
def stream(workspace):
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


@pytest.fixture
def client(owner):
    api = APIClient()
    api.force_authenticate(owner)
    return api


def _audit_url(workspace, query=''):
    return f'/api/workspaces/{workspace.id}/audit/{query}'


def _actions(workspace):
    return set(AuditEvent.objects.filter(workspace=workspace).values_list('action', flat=True))


def test_log_event_creates_db_row(workspace, owner):
    before = AuditEvent.objects.count()

    log_event(workspace=workspace, action='STREAM_CREATED', actor=owner, metadata={'k': 'v'}, ip_address='10.0.0.1')

    event = AuditEvent.objects.get()
    assert AuditEvent.objects.count() == before + 1
    assert event.actor == owner
    assert event.metadata == {'k': 'v'}
    assert str(event) == 'AuditEvent[STREAM_CREATED] by owner in w'


def test_log_event_never_raises(db, caplog):
    log_event(workspace=None, action='STREAM_CREATED')

    assert AuditEvent.objects.count() == 0
    assert 'AuditEvent write failed' in caplog.text


def test_get_client_ip_prefers_forwarded_header(rf):
    request = rf.get('/', HTTP_X_FORWARDED_FOR='1.2.3.4, 5.6.7.8', REMOTE_ADDR='9.9.9.9')
    assert get_client_ip(request) == '1.2.3.4'
    assert get_client_ip(rf.get('/', REMOTE_ADDR='9.9.9.9')) == '9.9.9.9'


def test_audit_api_requires_owner(workspace):
    member = User.objects.create_user('member', password='x')
    UserWorkspace.objects.create(user=member, workspace=workspace, role=UserWorkspace.ROLE_MEMBER)
    api = APIClient()
    api.force_authenticate(member)

    assert api.get(_audit_url(workspace)).status_code == 403


def test_audit_api_hidden_from_outsiders(workspace):
    outsider = User.objects.create_user('outsider', password='x')
    api = APIClient()
    api.force_authenticate(outsider)

    assert api.get(_audit_url(workspace)).status_code == 404


def test_audit_api_returns_events(client, workspace, owner):
    log_event(workspace=workspace, action='STREAM_CREATED', actor=owner)
    log_event(workspace=workspace, action='STREAM_PAUSED', actor=None)

    response = client.get(_audit_url(workspace))

    assert response.status_code == 200
    assert len(response.data) == 2
    assert {e['actor_username'] for e in response.data} == {'owner', None}


def test_audit_api_filter_by_action(client, workspace, owner):
    log_event(workspace=workspace, action='STREAM_CREATED', actor=owner)
    log_event(workspace=workspace, action='STREAM_PAUSED', actor=owner)

    response = client.get(_audit_url(workspace, '?action=STREAM_CREATED'))

    assert [e['action'] for e in response.data] == ['STREAM_CREATED']


def test_audit_api_isolated_between_workspaces(client, workspace, owner):
    other = Workspace.objects.create(name='O', slug='o', owner=owner)
    UserWorkspace.objects.create(user=owner, workspace=other, role=UserWorkspace.ROLE_OWNER)
    log_event(workspace=other, action='STREAM_CREATED', actor=owner)

    assert client.get(_audit_url(workspace)).data == []


def test_stream_create_emits_audit_event(client, workspace):
    response = client.post(
        '/api/streams/',
        {'workspace': workspace.id, 'name': 'New', 'source_type': Stream.SOURCE_SIMULATOR},
        format='json',
    )
    assert response.status_code == 201

    events = client.get(_audit_url(workspace, '?action=STREAM_CREATED')).data
    assert len(events) == 1
    assert events[0]['stream_name'] == 'New'


def test_stream_lifecycle_emits_audit_events(client, workspace, stream):
    client.post(f'/api/streams/{stream.id}/pause/')
    client.post(f'/api/streams/{stream.id}/resume/')
    client.post(f'/api/streams/{stream.id}/export/', {'type': 'DATAPOINTS'}, format='json')
    client.delete(f'/api/streams/{stream.id}/')

    assert _actions(workspace) >= {'STREAM_PAUSED', 'STREAM_RESUMED', 'EXPORT_REQUESTED', 'STREAM_DELETED'}
    deleted = AuditEvent.objects.get(action='STREAM_DELETED')
    assert deleted.metadata == {'stream_name': 'S'}
    assert deleted.stream is None


def test_lstm_training_emits_audit_event(client, workspace, stream, monkeypatch):
    Stream.objects.filter(pk=stream.pk).update(detector_type=Stream.DETECTOR_LSTM)

    class _Task:
        id = 'task-1'

    monkeypatch.setattr('detection.tasks.train_lstm_for_stream.delay', lambda stream_id: _Task())
    response = client.post(f'/api/streams/{stream.id}/train-lstm/')

    assert response.status_code == 202
    assert 'LSTM_TRAINING_TRIGGERED' in _actions(workspace)


def test_alert_acknowledge_emits_audit_event(client, workspace, stream):
    alert = Alert.objects.create(stream=stream, timestamp=timezone.now(), value=1.0, anomaly_score=4.0)

    response = client.post(f'/api/streams/{stream.id}/alerts/{alert.id}/acknowledge/')

    assert response.status_code == 200
    event = AuditEvent.objects.get(action='ALERT_ACKNOWLEDGED')
    assert event.metadata == {'alert_id': alert.id}
    assert event.stream == stream


def test_webhook_create_and_delete_emit_audit_events(client, workspace):
    created = client.post(
        '/api/webhooks/', {'workspace': workspace.id, 'name': 'hook', 'url': 'https://example.com/hook'}, format='json',
    )
    assert created.status_code == 201
    assert client.delete(f'/api/webhooks/{created.data["id"]}/').status_code == 204

    assert {'WEBHOOK_CREATED', 'WEBHOOK_DELETED'} <= _actions(workspace)
    assert not WebhookEndpoint.objects.exists()


def test_invite_emits_audit_event(client, workspace):
    client.post(f'/api/workspaces/{workspace.id}/invites/', {'email': 'n@example.com'}, format='json')

    event = AuditEvent.objects.get(action='MEMBER_INVITED')
    assert event.metadata == {'email': 'n@example.com', 'role': 'MEMBER'}
