from unittest.mock import patch

from django.utils import timezone

from alerts.services import create_alert
from detection.base import DetectionResult
from ingestion.models import DataPoint


def _result(severity='HIGH'):
    return DetectionResult(is_anomaly=True, score=3.5, severity=severity, value=99.0)


def _point(stream):
    return DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=99.0)


def test_slack_task_dispatched_on_root_alert(stream):
    with patch('integrations.tasks.dispatch_slack_notification.delay') as slack, \
            patch('integrations.tasks.dispatch_pagerduty_incident.delay'):
        alert = create_alert(stream, _point(stream), _result())

    slack.assert_called_once_with(alert.id)


def test_pagerduty_task_dispatched_on_root_alert(stream):
    with patch('integrations.tasks.dispatch_slack_notification.delay'), \
            patch('integrations.tasks.dispatch_pagerduty_incident.delay') as pagerduty:
        alert = create_alert(stream, _point(stream), _result())

    pagerduty.assert_called_once_with(alert.id)


def test_notification_tasks_not_dispatched_for_duplicate_alert(stream):
    with patch('integrations.tasks.dispatch_slack_notification.delay') as slack, \
            patch('integrations.tasks.dispatch_pagerduty_incident.delay') as pagerduty:
        create_alert(stream, _point(stream), _result())
        duplicate = create_alert(stream, _point(stream), _result())

    assert duplicate is None
    assert slack.call_count == 1
    assert pagerduty.call_count == 1


def test_notification_failure_does_not_block_alert_creation(stream):
    with patch('integrations.tasks.dispatch_slack_notification.delay', side_effect=RuntimeError('broker down')), \
            patch('integrations.tasks.dispatch_pagerduty_incident.delay') as pagerduty:
        alert = create_alert(stream, _point(stream), _result())

    assert alert is not None
    pagerduty.assert_called_once_with(alert.id)
