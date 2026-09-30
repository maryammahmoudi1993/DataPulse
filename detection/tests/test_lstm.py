import math

import pytest
from django.utils import timezone

from streams.models import Stream, Workspace

from detection.detectors.lstm import LSTMDetector, train_model
from detection.factory import get_detector
from detection.tasks import train_lstm_for_stream
from ingestion.models import DataPoint


def _sine(n):
    return [10.0 * math.sin(i * 0.3) for i in range(n)]


def test_lstm_without_model_never_fires():
    detector = LSTMDetector({'seq_len': 10})
    detector.fit(_sine(50))

    assert detector.detect(1000.0).is_anomaly is False


def test_train_requires_enough_data(tmp_path):
    with pytest.raises(ValueError):
        train_model([1.0] * 5, str(tmp_path / 'm.pt'), seq_len=10)


def test_lstm_detects_spike_after_training(tmp_path):
    path = str(tmp_path / 'model.pt')
    series = _sine(300)
    train_model(series, path, seq_len=10, epochs=60)

    detector = LSTMDetector({'seq_len': 10, 'threshold': 3.0, 'model_path': path})
    detector.fit(series)

    assert detector.detect(500.0).is_anomaly is True


def test_factory_returns_detector_for_each_type(db):
    workspace = Workspace.objects.create(name='W', slug='w')
    for detector_type in (Stream.DETECTOR_ZSCORE, Stream.DETECTOR_IQR, Stream.DETECTOR_LSTM):
        stream = Stream(workspace=workspace, name=detector_type, detector_type=detector_type)
        assert get_detector(stream) is not None


def test_train_task_registers_model_path(db, settings, tmp_path):
    settings.LSTM_MODEL_DIR = str(tmp_path)
    workspace = Workspace.objects.create(name='W', slug='w')
    stream = Stream.objects.create(
        workspace=workspace,
        name='S',
        source_type=Stream.SOURCE_SIMULATOR,
        detector_type=Stream.DETECTOR_LSTM,
        detector_config={'seq_len': 10},
    )
    DataPoint.objects.bulk_create(
        DataPoint(stream=stream, timestamp=timezone.now(), value=v) for v in _sine(220)
    )

    result = train_lstm_for_stream(stream.id, epochs=3)

    stream.refresh_from_db()
    assert result['status'] == 'ok'
    assert stream.detector_config['model_path'] == result['path']
