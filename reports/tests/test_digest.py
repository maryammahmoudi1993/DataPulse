from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import UserWorkspace
from alerts.models import Alert
from reports.tasks import _send_email, send_daily_alert_digest
from streams.models import Stream, Workspace

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def smtp(settings):
    settings.SMTP_USER = 'sender@example.com'
    settings.SMTP_PASSWORD = 'secret'
    with mock.patch('reports.tasks.smtplib.SMTP') as smtp_class:
        yield smtp_class.return_value.__enter__.return_value


def make_workspace(email='owner@example.com'):
    owner = User.objects.create_user(username='owner', password='testpass123', email=email)
    workspace = Workspace.objects.create(name='Acme', slug='acme', owner=owner)
    UserWorkspace.objects.create(user=owner, workspace=workspace, role=UserWorkspace.ROLE_OWNER)
    stream = Stream.objects.create(workspace=workspace, name='Sensor', source_type=Stream.SOURCE_SIMULATOR)
    return workspace, stream


def add_alert(stream, severity):
    return Alert.objects.create(
        stream=stream, timestamp=timezone.now(), value=1.0, anomaly_score=3.0,
        severity=severity, detector_type='ZSCORE',
    )


def test_digest_skips_workspace_with_no_alerts(smtp):
    make_workspace()

    result = send_daily_alert_digest()

    assert result == {'digests_sent': 0}
    smtp.send_message.assert_not_called()


def test_digest_skips_workspace_with_no_owner_email(smtp):
    _, stream = make_workspace(email='')
    add_alert(stream, Alert.SEVERITY_HIGH)

    result = send_daily_alert_digest()

    assert result == {'digests_sent': 0}
    smtp.send_message.assert_not_called()


def test_digest_body_contains_severity_counts(smtp):
    _, stream = make_workspace()
    for severity in (Alert.SEVERITY_HIGH, Alert.SEVERITY_HIGH, Alert.SEVERITY_LOW):
        add_alert(stream, severity)

    result = send_daily_alert_digest()

    assert result == {'digests_sent': 1}
    message = smtp.send_message.call_args.args[0]
    body = message.get_content()
    assert 'Total alerts: 3' in body
    assert 'High       2' in body
    assert 'Low        1' in body
    assert message['To'] == 'owner@example.com'
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with('sender@example.com', 'secret')


def test_digest_ignores_alerts_older_than_24_hours(smtp):
    _, stream = make_workspace()
    alert = add_alert(stream, Alert.SEVERITY_HIGH)
    Alert.objects.filter(pk=alert.pk).update(created_at=timezone.now() - timedelta(hours=30))

    assert send_daily_alert_digest() == {'digests_sent': 0}


def test_digest_not_counted_when_smtp_unconfigured(settings):
    settings.SMTP_USER = ''
    _, stream = make_workspace()
    add_alert(stream, Alert.SEVERITY_HIGH)

    assert send_daily_alert_digest() == {'digests_sent': 0}


def test_digest_delivery_failure_is_not_counted(smtp):
    _, stream = make_workspace()
    add_alert(stream, Alert.SEVERITY_HIGH)
    smtp.send_message.side_effect = OSError('connection refused')

    assert send_daily_alert_digest() == {'digests_sent': 0}


def test_send_email_returns_false_without_credentials(settings):
    settings.SMTP_USER = ''

    assert _send_email(['a@example.com'], 'subject', 'body') is False
