from detection.detectors.zscore import ZScoreDetector


def _make_history(mean=50.0, spread=1.0, size=30):
    return [mean + spread * ((-1) ** i) * (i % 3) for i in range(size)]


def test_normal_signal_no_anomaly():
    detector = ZScoreDetector()
    history = _make_history()
    detector.fit(history)

    result = detector.detect(50.0)

    assert result.is_anomaly is False


def test_spike_detected():
    detector = ZScoreDetector()
    history = _make_history()
    detector.fit(history)

    result = detector.detect(500.0)

    assert result.is_anomaly is True


def test_severity_low():
    detector = ZScoreDetector()

    severity = detector._classify_severity(1.0)

    assert severity == detector.SEVERITY_LOW


def test_severity_critical():
    detector = ZScoreDetector()

    severity = detector._classify_severity(5.0)

    assert severity == detector.SEVERITY_CRITICAL


def test_fit_with_short_history():
    detector = ZScoreDetector()
    detector.fit([1.0, 2.0])

    result = detector.detect(100.0)

    assert result.is_anomaly is False
    assert result.score == 0.0
