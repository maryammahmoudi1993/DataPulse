import pytest
from django.core.management import call_command
from django.utils import timezone

from alerts.models import Alert
from detection.pipeline import detect_and_alert
from ingestion.models import DataPoint
from streams.models import Stream, Workspace


@pytest.fixture
def stream(db):
    workspace = Workspace.objects.create(name='Test', slug='test')
    return Stream.objects.create(
        workspace=workspace,
        name='Test stream',
        source_type=Stream.SOURCE_SIMULATOR,
        detector_type=Stream.DETECTOR_ZSCORE,
        detector_config={'window': 30, 'threshold': 3.0},
    )


def test_full_pipeline_creates_alert(stream):
    """E2E: anomalous point → alert row in DB."""
    for i in range(50):
        DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=float(i % 5))

    point = DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=9999.0)

    detect_and_alert(point.id)

    assert Alert.objects.filter(stream=stream).exists()


def test_full_pipeline_no_alert_on_normal(stream):
    """Normal point within σ bounds → no alert created."""
    for _ in range(60):
        DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=5.0)

    point = DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=5.1)

    detect_and_alert(point.id)

    assert not Alert.objects.filter(stream=stream).exists()


def test_poll_stream_publishes_datapoint_event(stream):
    """Polling a stream stores a point and pushes it to the WebSocket group."""
    from unittest.mock import patch

    from ingestion.tasks import poll_stream

    with patch('ingestion.tasks.publish_stream_event') as publish:
        point_id = poll_stream(stream.id)

    stream_id, payload = publish.call_args.args
    assert stream_id == stream.id
    assert payload['type'] == 'datapoint'
    assert payload['id'] == point_id


def test_seed_demo_command(db):
    """seed_demo management command runs without error."""
    call_command('seed_demo', '--points', '50', '--flush')
    assert DataPoint.objects.filter(stream__workspace__slug='demo').count() == 50


def test_seed_demo_idempotent(db):
    """Running seed_demo twice does not raise."""
    call_command('seed_demo', '--points', '20', '--flush')
    call_command('seed_demo', '--points', '20')   # second run, no --flush
    assert DataPoint.objects.filter(stream__workspace__slug='demo').exists()
