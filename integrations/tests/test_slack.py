import json
from unittest.mock import MagicMock, patch

import requests

from integrations.models import NotificationLog, SlackIntegration
from integrations.tasks import dispatch_slack_notification

WEBHOOK = 'https://hooks.slack.com/services/T0/B0/xyz'


def _integration(workspace, **kwargs):
    return SlackIntegration.objects.create(workspace=workspace, webhook_url=WEBHOOK, **kwargs)


def test_slack_integration_created(workspace):
    integration = _integration(workspace, min_severity='HIGH')

    assert SlackIntegration.objects.get(pk=integration.pk).webhook_url == WEBHOOK
    assert integration.should_notify('CRITICAL') is True
    assert integration.should_notify('HIGH') is True
    assert integration.should_notify('LOW') is False


def test_dispatch_slack_notification_posts_to_webhook(workspace, make_alert):
    _integration(workspace)
    alert = make_alert('HIGH')

    with patch('integrations.slack.requests.post') as post:
        dispatch_slack_notification(alert.id)

    assert post.call_args.args[0] == WEBHOOK
    body = json.loads(post.call_args.kwargs['data'])
    assert body['blocks'][0]['type'] == 'header'
    assert 'HIGH' in body['text']
    assert post.call_args.kwargs['headers'] == {'Content-Type': 'application/json'}


def test_dispatch_slack_skips_below_min_severity(workspace, make_alert):
    _integration(workspace, min_severity='HIGH')
    alert = make_alert('LOW')

    with patch('integrations.slack.requests.post') as post:
        dispatch_slack_notification(alert.id)

    post.assert_not_called()
    log = NotificationLog.objects.get(alert=alert)
    assert log.status == NotificationLog.STATUS_SKIPPED
    assert log.channel == NotificationLog.CHANNEL_SLACK


def test_dispatch_slack_skips_when_inactive(workspace, make_alert):
    _integration(workspace, is_active=False)
    alert = make_alert('CRITICAL')

    with patch('integrations.slack.requests.post') as post:
        dispatch_slack_notification(alert.id)

    post.assert_not_called()
    assert not NotificationLog.objects.filter(alert=alert, status=NotificationLog.STATUS_OK).exists()


def test_dispatch_slack_logs_ok_on_success(workspace, make_alert):
    _integration(workspace)
    alert = make_alert('HIGH')

    with patch('integrations.slack.requests.post'):
        dispatch_slack_notification(alert.id)

    log = NotificationLog.objects.get(alert=alert)
    assert (log.status, log.channel, log.response_code) == (NotificationLog.STATUS_OK, 'SLACK', 200)


def test_dispatch_slack_logs_error_and_retries_on_failure(workspace, make_alert):
    _integration(workspace)
    alert = make_alert('HIGH')
    failure = requests.HTTPError('boom', response=MagicMock(status_code=500))

    with patch('integrations.slack.requests.post', side_effect=failure):
        try:
            dispatch_slack_notification(alert.id)
        except requests.HTTPError:
            pass

    logs = NotificationLog.objects.filter(alert=alert)
    assert logs.exists()
    assert set(logs.values_list('status', flat=True)) == {NotificationLog.STATUS_ERROR}
    assert logs.first().response_code == 500


def test_dispatch_slack_ignores_unknown_alert(db):
    dispatch_slack_notification(999999)

    assert NotificationLog.objects.count() == 0
