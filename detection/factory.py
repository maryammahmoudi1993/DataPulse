import os

from django.conf import settings

from streams.models import Stream

from detection.detectors.ensemble import EnsembleDetector
from detection.detectors.iqr import IQRDetector
from detection.detectors.lstm import LSTMDetector
from detection.detectors.zscore import ZScoreDetector

_DETECTORS = {
    Stream.DETECTOR_ZSCORE: ZScoreDetector,
    Stream.DETECTOR_IQR: IQRDetector,
    Stream.DETECTOR_LSTM: LSTMDetector,
}

DEFAULT_ENSEMBLE_MEMBERS = [
    {'type': Stream.DETECTOR_ZSCORE, 'weight': 0.4},
    {'type': Stream.DETECTOR_IQR, 'weight': 0.4},
    {'type': Stream.DETECTOR_LSTM, 'weight': 0.2},
]


def _build_ensemble(stream):
    """Build an EnsembleDetector from ``detector_config['members']``.

    Each member is ``{'type': ..., 'weight': ..., 'config': {...}}``. An LSTM
    member without an explicit ``model_path`` uses the stream's default
    checkpoint location.

    Raises:
        ValueError: If a member has an unknown or nested ensemble type.
    """
    members, weights = [], []
    for item in stream.detector_config.get('members', DEFAULT_ENSEMBLE_MEMBERS):
        detector_class = _DETECTORS.get(item['type'])
        if detector_class is None:
            raise ValueError(f'Unsupported ensemble member type: {item["type"]}')
        member_config = dict(item.get('config', {}))
        if item['type'] == Stream.DETECTOR_LSTM and stream.pk and 'model_path' not in member_config:
            member_config['model_path'] = os.path.join(settings.LSTM_MODEL_DIR, f'stream_{stream.pk}.pt')
        members.append(detector_class(member_config))
        weights.append(item['weight'])
    return EnsembleDetector(members, weights)


def get_detector(stream):
    if stream.detector_type == Stream.DETECTOR_ENSEMBLE:
        return _build_ensemble(stream)
    detector_class = _DETECTORS.get(stream.detector_type)
    if detector_class is None:
        raise ValueError(f'No detector registered for detector type: {stream.detector_type}')
    return detector_class(stream.detector_config)
