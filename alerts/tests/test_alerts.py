from unittest.mock import patch

import pytest
import requests
from django.utils import timezone

from alerts.models import Alert, WebhookEndpoint
from alerts.services import create_alert
from alerts.tasks import dispatch_webhooks
from detection.base import DetectionResult
from ingestion.models import DataPoint
from streams.models import Stream, Workspace


@pytest.fixture
def stream(db):
    workspace = Workspace.objects.create(name='W', slug='w')
    return Stream.objects.create(
        workspace=workspace,
        name='S',
        source_type=Stream.SOURCE_SIMULATOR,
        detector_type=Stream.DETECTOR_ZSCORE,
    )


def _result(severity='HIGH'):
    return DetectionResult(is_anomaly=True, score=3.5, severity=severity, value=99.0)


def _point(stream):
    return DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=99.0)


def _alert(stream):
    return Alert.objects.create(
        stream=stream, timestamp=timezone.now(), value=1.0, anomaly_score=4.0,
        severity='HIGH', detector_type='ZSCORE',
    )


def test_create_alert_persists_fields(stream):
    alert = create_alert(stream, _point(stream), _result())

    assert alert.severity == 'HIGH'
    assert alert.status == Alert.STATUS_OPEN
    assert alert.detector_type == Stream.DETECTOR_ZSCORE


def test_duplicate_alert_inside_window_is_suppressed(stream):
    create_alert(stream, _point(stream), _result())

    assert create_alert(stream, _point(stream), _result()) is None
    assert Alert.objects.count() == 1


def test_different_severity_is_not_deduplicated(stream):
    create_alert(stream, _point(stream), _result('HIGH'))

    assert create_alert(stream, _point(stream), _result('CRITICAL')) is not None


def test_alert_is_published_to_channel_layer(stream):
    with patch('alerts.services.publish_stream_event') as publish:
        alert = create_alert(stream, _point(stream), _result())

    payload = publish.call_args.args[1]
    assert payload['type'] == 'alert'
    assert payload['alert_id'] == alert.id


def test_webhook_severity_filter(stream):
    endpoint = WebhookEndpoint(workspace=stream.workspace, name='n', url='http://x.test', min_severity='HIGH')

    assert endpoint.accepts('CRITICAL') is True
    assert endpoint.accepts('LOW') is False


def test_dispatch_webhooks_signs_payload(stream):
    WebhookEndpoint.objects.create(
        workspace=stream.workspace, name='n', url='http://hook.test/x', min_severity='LOW', secret='signing-key',
    )
    alert = _alert(stream)

    with patch('alerts.tasks.requests.post') as post:
        delivered = dispatch_webhooks(alert.id)

    assert delivered == 1
    assert post.call_args.kwargs['headers']['X-DataPulse-Signature'].startswith('sha256=')


def test_dispatch_webhooks_survives_delivery_failure(stream):
    WebhookEndpoint.objects.create(workspace=stream.workspace, name='n', url='http://hook.test/x', min_severity='LOW')
    alert = _alert(stream)

    with patch('alerts.tasks.requests.post', side_effect=requests.ConnectionError('down')):
        assert dispatch_webhooks(alert.id) == 0


def test_string_representations(stream):
    alert = _alert(stream)
    endpoint = WebhookEndpoint.objects.create(workspace=stream.workspace, name='hook', url='http://a.test')

    assert 'HIGH' in str(alert)
    assert 'hook' in str(endpoint)
