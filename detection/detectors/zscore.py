import numpy as np

from detection.base import BaseDetector, DetectionResult


class ZScoreDetector(BaseDetector):
    """Flags a value as anomalous when it deviates too many standard
    deviations from the mean of recent history."""

    def __init__(self, config=None):
        super().__init__(config)
        self.threshold = self.config.get('threshold', 3.0)
        self.min_history = self.config.get('min_history', 10)
        self.mean = None
        self.std = None

    def fit(self, history):
        if len(history) < self.min_history:
            self.mean = None
            self.std = None
            return

        values = np.array(history, dtype=float)
        self.mean = float(np.mean(values))
        self.std = float(np.std(values))

    def detect(self, value):
        if self.mean is None or self.std is None or self.std == 0:
            return DetectionResult(
                is_anomaly=False,
                score=0.0,
                severity=self.SEVERITY_LOW,
                value=value,
            )

        score = abs(value - self.mean) / self.std
        is_anomaly = score >= self.threshold
        severity = self._classify_severity(score)

        return DetectionResult(
            is_anomaly=is_anomaly,
            score=score,
            severity=severity,
            value=value,
        )
