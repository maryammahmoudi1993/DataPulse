import math

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from detection.tasks import train_lstm_for_stream
from ingestion.models import DataPoint
from streams.models import Stream, Workspace


@pytest.fixture
def lstm_stream(db, settings, tmp_path):
    settings.LSTM_MODEL_DIR = str(tmp_path)
    owner = get_user_model().objects.create_user('owner', password='x')
    workspace = Workspace.objects.create(name='W', slug='w', owner=owner)
    return Stream.objects.create(
        workspace=workspace,
        name='S',
        source_type=Stream.SOURCE_SIMULATOR,
        detector_type=Stream.DETECTOR_LSTM,
        detector_config={'seq_len': 10},
    )


def _seed(stream, count):
    DataPoint.objects.bulk_create(
        DataPoint(stream=stream, timestamp=timezone.now(), value=10 * math.sin(i * 0.3))
        for i in range(count)
    )


def test_train_lstm_task_skips_insufficient_data(lstm_stream):
    _seed(lstm_stream, 50)

    result = train_lstm_for_stream(lstm_stream.id, epochs=1)

    lstm_stream.refresh_from_db()
    assert result['status'] == 'skipped'
    assert 'model_path' not in lstm_stream.detector_config


def test_train_lstm_updates_stream_config(lstm_stream):
    _seed(lstm_stream, 220)

    result = train_lstm_for_stream(lstm_stream.id, epochs=2)

    lstm_stream.refresh_from_db()
    assert result['status'] == 'ok'
    assert result['samples'] > 0
    assert lstm_stream.detector_config['model_path'] == result['path']


def test_train_lstm_task_handles_missing_stream(db):
    assert train_lstm_for_stream(999999)['status'] == 'missing'


def test_train_lstm_action_returns_task_id(lstm_stream):
    client = APIClient()
    client.force_authenticate(user=lstm_stream.workspace.owner)

    response = client.post(f'/api/streams/{lstm_stream.id}/train-lstm/')

    assert response.status_code == 202
    assert response.data['task_id']


def test_train_lstm_action_rejects_other_detectors(lstm_stream):
    lstm_stream.detector_type = Stream.DETECTOR_ZSCORE
    lstm_stream.save()
    client = APIClient()
    client.force_authenticate(user=lstm_stream.workspace.owner)

    response = client.post(f'/api/streams/{lstm_stream.id}/train-lstm/')

    assert response.status_code == 400


def test_training_status_requires_task_id(lstm_stream):
    client = APIClient()
    client.force_authenticate(user=lstm_stream.workspace.owner)

    response = client.get(f'/api/streams/{lstm_stream.id}/training-status/')

    assert response.status_code == 400


def test_training_status_reports_state(lstm_stream):
    client = APIClient()
    client.force_authenticate(user=lstm_stream.workspace.owner)

    response = client.get(f'/api/streams/{lstm_stream.id}/training-status/?task_id=unknown-task')

    assert response.status_code == 200
    assert response.data['state'] == 'PENDING'
    assert response.data['result'] is None
