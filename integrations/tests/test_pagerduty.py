from unittest.mock import MagicMock, patch

import pytest
import requests

from integrations.models import NotificationLog, PagerDutyIntegration
from integrations.pagerduty import PAGERDUTY_EVENTS_URL, PD_SEVERITY_MAP
from integrations.tasks import dispatch_pagerduty_incident


def _integration(workspace, **kwargs):
    return PagerDutyIntegration.objects.create(workspace=workspace, routing_key='rk-123', **kwargs)


def test_pagerduty_integration_created(workspace):
    integration = _integration(workspace)

    stored = PagerDutyIntegration.objects.get(pk=integration.pk)
    assert stored.routing_key == 'rk-123'
    assert stored.min_severity == 'HIGH'
    assert stored.is_active is True


def test_dispatch_pagerduty_posts_to_events_api(workspace, make_alert):
    _integration(workspace)
    alert = make_alert('CRITICAL')

    with patch('integrations.pagerduty.requests.post') as post:
        post.return_value.json.return_value = {'status': 'success'}
        dispatch_pagerduty_incident(alert.id)

    assert post.call_args.args[0] == PAGERDUTY_EVENTS_URL
    assert 'events.pagerduty.com' in post.call_args.args[0]
    payload = post.call_args.kwargs['json']
    assert payload['routing_key'] == 'rk-123'
    assert payload['dedup_key'] == f'datapulse-alert-{alert.id}'
    assert payload['payload']['custom_details']['alert_id'] == alert.id
    log = NotificationLog.objects.get(alert=alert)
    assert (log.status, log.channel, log.response_code) == (NotificationLog.STATUS_OK, 'PAGERDUTY', 202)


@pytest.mark.parametrize('severity,expected', [
    ('CRITICAL', 'critical'), ('HIGH', 'error'), ('MEDIUM', 'warning'), ('LOW', 'info'),
])
def test_pagerduty_severity_mapping(workspace, make_alert, severity, expected):
    _integration(workspace, min_severity='LOW')
    alert = make_alert(severity)

    with patch('integrations.pagerduty.requests.post') as post:
        post.return_value.json.return_value = {}
        dispatch_pagerduty_incident(alert.id)

    assert PD_SEVERITY_MAP[severity] == expected
    assert post.call_args.kwargs['json']['payload']['severity'] == expected


def test_dispatch_pagerduty_skips_below_min_severity(workspace, make_alert):
    _integration(workspace, min_severity='CRITICAL')
    alert = make_alert('MEDIUM')

    with patch('integrations.pagerduty.requests.post') as post:
        dispatch_pagerduty_incident(alert.id)

    post.assert_not_called()
    assert NotificationLog.objects.get(alert=alert).status == NotificationLog.STATUS_SKIPPED


def test_dispatch_pagerduty_logs_error_on_failure(workspace, make_alert):
    _integration(workspace)
    alert = make_alert('HIGH')
    failure = requests.ConnectionError('down')
    failure.response = MagicMock(status_code=503)

    with patch('integrations.pagerduty.requests.post', side_effect=failure):
        with pytest.raises(requests.RequestException):
            dispatch_pagerduty_incident(alert.id)

    log = NotificationLog.objects.filter(alert=alert).first()
    assert log.status == NotificationLog.STATUS_ERROR
    assert log.response_code == 503
    assert 'down' in log.error
