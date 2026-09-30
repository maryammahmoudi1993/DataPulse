import numpy as np

from detection.base import BaseDetector, DetectionResult


class IQRDetector(BaseDetector):
    """Flags values outside the Tukey fences of a rolling window.

    Config keys: ``window`` (default 100), ``multiplier`` (default 1.5) and
    ``min_history`` (default 10). The score is a robust z-score based on the
    median and the interquartile range, so it is comparable to Z-score output.
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.window = self.config.get('window', 100)
        self.multiplier = self.config.get('multiplier', 1.5)
        self.min_history = self.config.get('min_history', 10)
        self.q1 = None
        self.q3 = None
        self.median = None

    def fit(self, history):
        recent = list(history)[-self.window:]
        if len(recent) < self.min_history:
            self.q1 = self.q3 = self.median = None
            return

        values = np.array(recent, dtype=float)
        self.q1, self.median, self.q3 = (float(x) for x in np.percentile(values, [25, 50, 75]))

    def detect(self, value):
        if self.q1 is None or self.q3 - self.q1 == 0:
            return DetectionResult(
                is_anomaly=False,
                score=0.0,
                severity=self.SEVERITY_LOW,
                value=value,
            )

        iqr = self.q3 - self.q1
        lower = self.q1 - self.multiplier * iqr
        upper = self.q3 + self.multiplier * iqr
        score = abs(value - self.median) / (iqr / 1.349)

        return DetectionResult(
            is_anomaly=value < lower or value > upper,
            score=score,
            severity=self._classify_severity(score),
            value=value,
        )
