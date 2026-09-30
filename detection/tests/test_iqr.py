import pytest

from detection.detectors.iqr import IQRDetector

HISTORY = [10.0, 11.0, 9.0, 10.5, 9.5, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0]


def test_iqr_flags_outlier():
    detector = IQRDetector({'min_history': 5})
    detector.fit(HISTORY)

    result = detector.detect(50.0)

    assert result.is_anomaly is True
    assert result.score > 3


def test_iqr_accepts_normal_value():
    detector = IQRDetector({'min_history': 5})
    detector.fit(HISTORY)

    assert detector.detect(10.1).is_anomaly is False


def test_iqr_needs_minimum_history():
    detector = IQRDetector({'min_history': 20})
    detector.fit(HISTORY)

    assert detector.detect(1000.0).is_anomaly is False


def test_iqr_constant_history_never_fires():
    detector = IQRDetector({'min_history': 5})
    detector.fit([5.0] * 30)

    assert detector.detect(6.0).is_anomaly is False


@pytest.mark.parametrize('multiplier, expected', [(1.5, True), (100.0, False)])
def test_iqr_multiplier_widens_fences(multiplier, expected):
    detector = IQRDetector({'min_history': 5, 'multiplier': multiplier})
    detector.fit(HISTORY)

    assert detector.detect(13.0).is_anomaly is expected
