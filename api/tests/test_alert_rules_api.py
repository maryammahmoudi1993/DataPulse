from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from alerts.models import AlertRule
from audit.models import AuditEvent
from streams.models import Stream, StreamRollup, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='x')


@pytest.fixture
def stream(owner):
    workspace = Workspace.objects.create(name='W', slug='w', owner=owner)
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


@pytest.fixture
def client(owner):
    api = APIClient()
    api.force_authenticate(owner)
    return api


def _payload(**overrides):
    return {'name': 'High temp', 'condition': 'ABOVE', 'threshold': 80, **overrides}


def test_create_alert_rule(client, stream, owner):
    response = client.post(f'/api/streams/{stream.id}/rules/', _payload(severity='CRITICAL'), format='json')

    assert response.status_code == 201
    rule = AlertRule.objects.get(pk=response.data['id'])
    assert (rule.stream, rule.created_by, rule.severity) == (stream, owner, 'CRITICAL')
    assert AuditEvent.objects.filter(action='ALERT_RULE_CREATED', stream=stream).exists()


def test_create_ignores_stream_in_body(client, stream):
    other = Stream.objects.create(workspace=stream.workspace, name='Other', source_type=Stream.SOURCE_SIMULATOR)

    response = client.post(f'/api/streams/{stream.id}/rules/', _payload(stream=other.id), format='json')

    assert AlertRule.objects.get(pk=response.data['id']).stream == stream


def test_list_alert_rules_scoped_to_stream(client, stream):
    other = Stream.objects.create(workspace=stream.workspace, name='Other', source_type=Stream.SOURCE_SIMULATOR)
    AlertRule.objects.create(stream=stream, name='mine', condition='ABOVE', threshold=1)
    AlertRule.objects.create(stream=other, name='theirs', condition='ABOVE', threshold=1)

    response = client.get(f'/api/streams/{stream.id}/rules/')

    assert [r['name'] for r in response.data] == ['mine']


def test_outsider_cannot_see_or_create_rules(stream):
    outsider = APIClient()
    outsider.force_authenticate(User.objects.create_user('outsider', password='x'))
    AlertRule.objects.create(stream=stream, name='mine', condition='ABOVE', threshold=1)

    assert outsider.get(f'/api/streams/{stream.id}/rules/').data == []
    assert outsider.post(f'/api/streams/{stream.id}/rules/', _payload(), format='json').status_code == 404


def test_update_rule_threshold(client, stream):
    rule = AlertRule.objects.create(stream=stream, name='r', condition='ABOVE', threshold=1)

    response = client.patch(f'/api/streams/{stream.id}/rules/{rule.id}/', {'threshold': 99}, format='json')

    assert response.status_code == 200
    rule.refresh_from_db()
    assert rule.threshold == 99


def test_delete_rule(client, stream):
    rule = AlertRule.objects.create(stream=stream, name='r', condition='ABOVE', threshold=1)

    response = client.delete(f'/api/streams/{stream.id}/rules/{rule.id}/')

    assert response.status_code == 204
    assert not AlertRule.objects.exists()


def test_rollups_endpoint_returns_newest_first(client, stream):
    base = timezone.now().replace(minute=0, second=0, microsecond=0)
    for hours in (3, 2, 1):
        StreamRollup.objects.create(
            stream=stream, period='HOURLY', bucket_ts=base - timedelta(hours=hours),
            count=1, mean=1, std=0, min_val=1, max_val=1, p50=1, p95=1, p99=1,
        )

    response = client.get(f'/api/streams/{stream.id}/analytics/rollups/?limit=2')

    assert response.status_code == 200
    assert len(response.data) == 2
    assert response.data[0]['bucket_ts'] > response.data[1]['bucket_ts']


@pytest.mark.parametrize('path', [
    'analytics/rollups/?period=WEEKLY',
    'analytics/rollups/?limit=abc',
    'analytics/moving-average/?window=0',
    'analytics/trend/?last_n=-5',
    'analytics/alert-rate/?hours=x',
])
def test_invalid_analytics_params_return_400(client, stream, path):
    assert client.get(f'/api/streams/{stream.id}/{path}').status_code == 400


def test_analytics_endpoints_respond(client, stream):
    for path in ('moving-average', 'trend', 'alert-rate'):
        assert client.get(f'/api/streams/{stream.id}/analytics/{path}/').status_code == 200
