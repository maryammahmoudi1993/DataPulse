import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from audit.models import AuditEvent
from integrations.models import NotificationLog, PagerDutyIntegration, SlackIntegration
from streams.models import Workspace

User = get_user_model()

SLACK_URL = '/api/integrations/slack/'
PD_URL = '/api/integrations/pagerduty/'


@pytest.fixture
def client(owner):
    api_client = APIClient()
    api_client.force_authenticate(owner)
    return api_client


def test_slack_create_hides_webhook_url_and_audits(client, workspace):
    response = client.post(SLACK_URL, {
        'workspace': workspace.id, 'webhook_url': 'https://hooks.slack.com/services/a', 'min_severity': 'HIGH',
    })

    assert response.status_code == 201
    assert 'webhook_url' not in response.data
    assert AuditEvent.objects.filter(workspace=workspace, metadata={'channel': 'SLACK'}).exists()
    listing = client.get(f'{SLACK_URL}?workspace={workspace.id}')
    assert [row['id'] for row in listing.data] == [response.data['id']]
    assert 'webhook_url' not in listing.data[0]


def test_pagerduty_create_hides_routing_key(client, workspace):
    response = client.post(PD_URL, {'workspace': workspace.id, 'routing_key': 'secret-key'})

    assert response.status_code == 201
    assert 'routing_key' not in response.data
    assert PagerDutyIntegration.objects.get(workspace=workspace).routing_key == 'secret-key'


def test_patch_updates_without_resending_secret(client, workspace):
    created = client.post(SLACK_URL, {'workspace': workspace.id, 'webhook_url': 'https://hooks.slack.com/a'})

    response = client.patch(f'{SLACK_URL}{created.data["id"]}/', {'min_severity': 'LOW', 'is_active': False})

    assert response.status_code == 200
    stored = SlackIntegration.objects.get(workspace=workspace)
    assert (stored.min_severity, stored.is_active) == ('LOW', False)
    assert stored.webhook_url == 'https://hooks.slack.com/a'


def test_patch_cannot_move_integration_to_another_workspace(client, workspace, owner):
    other = Workspace.objects.create(name='O', slug='o', owner=owner)
    created = client.post(SLACK_URL, {'workspace': workspace.id, 'webhook_url': 'https://hooks.slack.com/a'})

    client.patch(f'{SLACK_URL}{created.data["id"]}/', {'workspace': other.id})

    assert SlackIntegration.objects.get(pk=created.data['id']).workspace_id == workspace.id


def test_second_integration_for_workspace_is_rejected(client, workspace):
    body = {'workspace': workspace.id, 'webhook_url': 'https://hooks.slack.com/a'}
    client.post(SLACK_URL, body)

    assert client.post(SLACK_URL, body).status_code == 400


def test_invalid_min_severity_is_rejected(client, workspace):
    response = client.post(SLACK_URL, {
        'workspace': workspace.id, 'webhook_url': 'https://hooks.slack.com/a', 'min_severity': 'EXTREME',
    })

    assert response.status_code == 400


def test_cannot_create_integration_in_foreign_workspace(client):
    stranger = User.objects.create_user('stranger', password='x')
    foreign = Workspace.objects.create(name='F', slug='f', owner=stranger)

    response = client.post(SLACK_URL, {'workspace': foreign.id, 'webhook_url': 'https://hooks.slack.com/a'})

    assert response.status_code == 404
    assert not SlackIntegration.objects.exists()


def test_integrations_require_authentication(workspace):
    assert APIClient().get(SLACK_URL).status_code == 401
    assert APIClient().get('/api/integrations/notifications/').status_code == 401


def test_notification_log_lists_only_own_workspaces(client, make_alert):
    alert = make_alert()
    NotificationLog.objects.create(alert=alert, channel='SLACK', status='OK', response_code=200)
    stranger = APIClient()
    stranger.force_authenticate(User.objects.create_user('stranger', password='x'))

    mine = client.get('/api/integrations/notifications/')

    assert [row['alert'] for row in mine.data] == [alert.id]
    assert stranger.get('/api/integrations/notifications/').data == []
    assert client.post('/api/integrations/notifications/', {}).status_code == 405
