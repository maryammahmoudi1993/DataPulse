import csv
import os
from datetime import timedelta
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from alerts.models import Alert
from exports.models import ExportJob
from exports.tasks import cleanup_stale_exports, run_export
from ingestion.models import DataPoint
from streams.models import Stream, Workspace

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def export_root(settings, tmp_path):
    settings.EXPORT_ROOT = str(tmp_path / 'exports')
    return settings.EXPORT_ROOT


@pytest.fixture
def user():
    return User.objects.create_user(username='maryam', password='testpass123')


@pytest.fixture
def stream(user):
    workspace = Workspace.objects.create(name='Acme', slug='acme', owner=user)
    return Stream.objects.create(workspace=workspace, name='Sensor', source_type=Stream.SOURCE_SIMULATOR)


@pytest.fixture
def client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def read_csv(path):
    with open(path, newline='') as f:
        return list(csv.reader(f))


def test_export_job_creates_with_pending_status(client, stream):
    with mock.patch('api.views.run_export.delay') as delay:
        response = client.post(f'/api/streams/{stream.id}/export/', {'type': 'DATAPOINTS'}, format='json')

    assert response.status_code == 202
    job = ExportJob.objects.get(pk=response.data['job_id'])
    assert job.status == ExportJob.STATUS_PENDING
    assert job.stream == stream
    delay.assert_called_once_with(job.id)


def test_export_rejects_unknown_type(client, stream):
    response = client.post(f'/api/streams/{stream.id}/export/', {'type': 'NOPE'}, format='json')

    assert response.status_code == 400
    assert not ExportJob.objects.exists()


def test_run_export_datapoints_creates_csv(stream):
    now = timezone.now()
    for i in range(3):
        DataPoint.objects.create(stream=stream, timestamp=now + timedelta(seconds=i), value=float(i))
    job = ExportJob.objects.create(stream=stream, export_type=ExportJob.TYPE_DATAPOINTS)

    run_export(job.id)

    job.refresh_from_db()
    assert job.status == ExportJob.STATUS_DONE
    assert job.row_count == 3
    rows = read_csv(job.file_path)
    assert rows[0] == ['id', 'timestamp', 'value']
    assert [r[2] for r in rows[1:]] == ['0.0', '1.0', '2.0']


def test_run_export_alerts_creates_csv(stream):
    Alert.objects.create(
        stream=stream, timestamp=timezone.now(), value=9.0, anomaly_score=4.5,
        severity=Alert.SEVERITY_CRITICAL, detector_type='ZSCORE',
    )
    job = ExportJob.objects.create(stream=stream, export_type=ExportJob.TYPE_ALERTS)

    run_export(job.id)

    job.refresh_from_db()
    rows = read_csv(job.file_path)
    assert rows[0] == ['id', 'timestamp', 'value', 'anomaly_score', 'severity', 'detector_type', 'status']
    assert rows[1][4] == 'CRITICAL'
    assert job.row_count == 1


def test_run_export_marks_job_failed_on_error(stream):
    job = ExportJob.objects.create(stream=stream, export_type=ExportJob.TYPE_DATAPOINTS)

    with mock.patch('exports.tasks._export_datapoints', side_effect=OSError('disk full')):
        with pytest.raises(OSError):
            run_export(job.id)

    job.refresh_from_db()
    assert job.status == ExportJob.STATUS_FAILED
    assert 'disk full' in job.error


def test_run_export_ignores_missing_job():
    assert run_export(999999) is None


def test_export_pipeline_end_to_end(client, stream):
    DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=1.5)

    created = client.post(f'/api/streams/{stream.id}/export/', {'type': 'DATAPOINTS'}, format='json')
    job_id = created.data['job_id']
    status_response = client.get(f'/api/streams/{stream.id}/export/{job_id}/')
    download = client.get(status_response.data['download_url'])

    assert status_response.data['status'] == ExportJob.STATUS_DONE
    assert status_response.data['row_count'] == 1
    assert download.status_code == 200
    assert download['Content-Disposition'].endswith(f'stream_{stream.id}_datapoints.csv"')
    assert b'id,timestamp,value' in b''.join(download.streaming_content)


def test_export_status_unknown_job_is_404(client, stream):
    assert client.get(f'/api/streams/{stream.id}/export/12345/').status_code == 404


def test_download_returns_404_when_not_ready(client, stream):
    job = ExportJob.objects.create(stream=stream, export_type=ExportJob.TYPE_DATAPOINTS)

    assert client.get(f'/api/streams/{stream.id}/export/{job.id}/download/').status_code == 404


def test_download_returns_410_when_file_missing(client, stream):
    DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=1.0)
    job = ExportJob.objects.create(stream=stream, export_type=ExportJob.TYPE_DATAPOINTS)
    run_export(job.id)
    job.refresh_from_db()
    os.remove(job.file_path)

    response = client.get(f'/api/streams/{stream.id}/export/{job.id}/download/')

    assert response.status_code == 410


def test_export_is_scoped_to_workspace(stream):
    outsider = User.objects.create_user(username='eve', password='testpass123')
    client = APIClient()
    client.force_authenticate(user=outsider)

    response = client.post(f'/api/streams/{stream.id}/export/', {'type': 'ALERTS'}, format='json')

    assert response.status_code == 404


def test_cleanup_stale_exports_deletes_old(stream):
    old = ExportJob.objects.create(stream=stream, export_type=ExportJob.TYPE_DATAPOINTS)
    fresh = ExportJob.objects.create(stream=stream, export_type=ExportJob.TYPE_DATAPOINTS)
    run_export(old.id)
    old.refresh_from_db()
    ExportJob.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(hours=48))

    deleted = cleanup_stale_exports()

    assert deleted == 1
    assert not os.path.exists(old.file_path)
    assert not ExportJob.objects.filter(pk=old.pk).exists()
    assert ExportJob.objects.filter(pk=fresh.pk).exists()


def test_export_job_str(stream):
    job = ExportJob.objects.create(stream=stream, export_type=ExportJob.TYPE_ALERTS)

    assert str(job) == f'Export[ALERTS] stream={stream.id} PENDING'
