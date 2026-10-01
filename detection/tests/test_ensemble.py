import pytest

from detection.base import BaseDetector, DetectionResult
from detection.detectors.ensemble import EnsembleDetector
from detection.factory import get_detector
from streams.models import Stream


class StubDetector(BaseDetector):
    """Detector returning a fixed verdict."""

    def __init__(self, is_anomaly, score):
        super().__init__()
        self._is_anomaly = is_anomaly
        self._score = score
        self.fitted_with = None

    def fit(self, history):
        self.fitted_with = history

    def detect(self, value):
        return DetectionResult(self._is_anomaly, self._score, self.SEVERITY_LOW, value)


def test_majority_vote_anomaly():
    ensemble = EnsembleDetector([StubDetector(True, 3.0), StubDetector(True, 3.0), StubDetector(False, 0.0)])

    assert ensemble.detect(10.0).is_anomaly is True


def test_minority_vote_no_anomaly():
    ensemble = EnsembleDetector([StubDetector(True, 5.0), StubDetector(False, 0.0), StubDetector(False, 0.0)])

    assert ensemble.detect(10.0).is_anomaly is False


def test_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        EnsembleDetector([StubDetector(True, 1.0), StubDetector(False, 0.0)], weights=[0.5, 0.2])


def test_empty_detectors_raises():
    with pytest.raises(ValueError):
        EnsembleDetector([])


def test_weight_count_must_match_detectors():
    with pytest.raises(ValueError):
        EnsembleDetector([StubDetector(True, 1.0), StubDetector(False, 0.0)], weights=[1.0])


def test_ensemble_score_is_weighted_mean():
    ensemble = EnsembleDetector([StubDetector(True, 4.0), StubDetector(False, 1.0)], weights=[0.75, 0.25])

    result = ensemble.detect(7.0)

    assert result.score == pytest.approx(3.25)
    assert result.value == 7.0
    assert result.severity == BaseDetector.SEVERITY_HIGH


def test_fit_is_forwarded_to_members():
    members = [StubDetector(False, 0.0), StubDetector(False, 0.0)]

    EnsembleDetector(members).fit([1.0, 2.0])

    assert all(m.fitted_with == [1.0, 2.0] for m in members)


def test_factory_builds_default_ensemble():
    stream = Stream(detector_type=Stream.DETECTOR_ENSEMBLE, detector_config={})

    detector = get_detector(stream)

    assert isinstance(detector, EnsembleDetector)
    assert len(detector.detectors) == 3
    assert detector.weights == [0.4, 0.4, 0.2]


def test_factory_rejects_nested_ensemble_member():
    stream = Stream(
        detector_type=Stream.DETECTOR_ENSEMBLE,
        detector_config={'members': [{'type': Stream.DETECTOR_ENSEMBLE, 'weight': 1.0}]},
    )

    with pytest.raises(ValueError):
        get_detector(stream)


def test_ensemble_flags_spike_end_to_end():
    stream = Stream(
        detector_type=Stream.DETECTOR_ENSEMBLE,
        detector_config={'members': [
            {'type': Stream.DETECTOR_ZSCORE, 'weight': 0.5},
            {'type': Stream.DETECTOR_IQR, 'weight': 0.5},
        ]},
    )
    detector = get_detector(stream)
    detector.fit([50.0 + i % 2 for i in range(40)])

    assert detector.detect(5000.0).is_anomaly is True
    assert detector.detect(50.5).is_anomaly is False
