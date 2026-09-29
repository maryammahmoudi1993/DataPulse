import pytest
from django.utils import timezone

from streams.models import Stream, Workspace

from detection.pipeline import detect_and_alert
from ingestion.models import DataPoint


@pytest.fixture
def stream(db):
    workspace = Workspace.objects.create(name='Acme Corp', slug='acme-corp')
    return Stream.objects.create(
        workspace=workspace,
        name='Sensor',
        source_type=Stream.SOURCE_SIMULATOR,
        detector_type=Stream.DETECTOR_ZSCORE,
        detector_config={'min_history': 5},
    )


@pytest.mark.django_db
def test_detect_and_alert_marks_anomaly(stream):
    now = timezone.now()
    for i in range(10):
        DataPoint.objects.create(stream=stream, timestamp=now, value=50.0 + i % 2)

    spike = DataPoint.objects.create(stream=stream, timestamp=now, value=5000.0)

    result = detect_and_alert(spike.id)

    spike.refresh_from_db()
    assert result['is_anomaly'] is True
    assert spike.metadata.get('anomaly') is True


@pytest.mark.django_db
def test_detect_and_alert_missing_point():
    result = detect_and_alert(999999)

    assert result is None
