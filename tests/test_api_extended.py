import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from alerts.models import Alert
from ingestion.models import DataPoint
from streams.models import Stream, Workspace


@pytest.fixture
def auth_client(db):
    user = User.objects.create_user('testuser', password='pass')
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user


@pytest.fixture
def stream_with_alerts(db, auth_client):
    _, user = auth_client
    workspace = Workspace.objects.create(name='W', slug='w')
    workspace.members.add(user)
    stream = Stream.objects.create(
        workspace=workspace, name='S',
        source_type=Stream.SOURCE_SIMULATOR,
        detector_type=Stream.DETECTOR_ZSCORE,
    )
    point = DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=99.0)
    Alert.objects.create(
        stream=stream, data_point=point, timestamp=timezone.now(), value=99.0,
        anomaly_score=5.0, severity=Alert.SEVERITY_HIGH, detector_type='ZSCORE',
    )
    Alert.objects.create(
        stream=stream, timestamp=timezone.now(), value=1.0,
        anomaly_score=1.0, severity=Alert.SEVERITY_LOW, detector_type='ZSCORE',
    )
    return stream


def test_alert_filter_by_severity(auth_client, stream_with_alerts):
    client, _ = auth_client
    response = client.get(f'/api/streams/{stream_with_alerts.id}/alerts/?severity=HIGH')
    assert response.status_code == 200
    assert len(response.data) == 1
    assert all(a['severity'] == 'HIGH' for a in response.data)


def test_alert_filter_by_status(auth_client, stream_with_alerts):
    client, _ = auth_client
    response = client.get(f'/api/streams/{stream_with_alerts.id}/alerts/?status=OPEN')
    assert response.status_code == 200
    assert len(response.data) == 2
    assert all(a['status'] == 'OPEN' for a in response.data)


def test_alert_acknowledge(auth_client, stream_with_alerts):
    client, user = auth_client
    alert = Alert.objects.filter(stream=stream_with_alerts).first()
    response = client.post(f'/api/streams/{stream_with_alerts.id}/alerts/{alert.id}/acknowledge/')
    assert response.status_code == 200
    alert.refresh_from_db()
    assert alert.status == Alert.STATUS_ACKNOWLEDGED
    assert alert.acknowledged_by == user


def test_datapoints_limit(auth_client, stream_with_alerts):
    client, _ = auth_client
    for _ in range(5):
        DataPoint.objects.create(stream=stream_with_alerts, timestamp=timezone.now(), value=1.0)
    response = client.get(f'/api/streams/{stream_with_alerts.id}/datapoints/?limit=3')
    assert response.status_code == 200
    assert len(response.data) == 3
