import pytest
from django.test import Client
from django.utils import timezone

from detection.pipeline import detect_and_alert
from ingestion.models import DataPoint
from streams.models import Stream, Workspace


@pytest.mark.django_db
def test_metrics_endpoint_is_public_and_reports_active_streams():
    workspace = Workspace.objects.create(name='Acme', slug='acme')
    Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)

    response = Client().get('/metrics/')

    assert response.status_code == 200
    body = response.content.decode()
    assert 'datapulse_active_streams 1.0' in body
    assert 'datapulse_detection_latency_seconds' in body


@pytest.mark.django_db
def test_detection_pipeline_records_metrics():
    workspace = Workspace.objects.create(name='Acme', slug='acme')
    stream = Stream.objects.create(
        workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR,
        detector_config={'min_history': 5},
    )
    now = timezone.now()
    for i in range(10):
        DataPoint.objects.create(stream=stream, timestamp=now, value=50.0 + i % 2)
    spike = DataPoint.objects.create(stream=stream, timestamp=now, value=5000.0)

    detect_and_alert(spike.id)

    body = Client().get('/metrics/').content.decode()
    assert 'datapulse_anomalies_detected_total{detector_type="ZSCORE",severity="CRITICAL"}' in body
    assert 'datapulse_alerts_created_total{severity="CRITICAL"}' in body
