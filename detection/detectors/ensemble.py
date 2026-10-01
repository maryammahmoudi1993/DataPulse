import numpy as np

from detection.base import BaseDetector, DetectionResult


class EnsembleDetector(BaseDetector):
    """Combines several detectors through a weighted majority vote.

    The anomaly score is the weighted mean of the member scores. A value is
    flagged only when strictly more than half of the members flag it.
    """

    def __init__(self, detectors, weights=None, config=None):
        """Build the ensemble.

        Args:
            detectors: Non-empty list of member detectors.
            weights: One weight per member summing to 1.0. Defaults to equal weights.
            config: Optional detector config.

        Raises:
            ValueError: If there are no detectors, the weights do not match
                the detectors in number, or the weights do not sum to 1.0.
        """
        super().__init__(config)
        if not detectors:
            raise ValueError('EnsembleDetector requires at least one detector.')
        self.detectors = list(detectors)
        self.weights = list(weights) if weights is not None else [1.0 / len(self.detectors)] * len(self.detectors)
        if len(self.weights) != len(self.detectors):
            raise ValueError('Provide exactly one weight per detector.')
        if abs(sum(self.weights) - 1.0) > 1e-6:
            raise ValueError('Weights must sum to 1.0')

    def fit(self, history):
        """Fit every member on the same history."""
        for detector in self.detectors:
            detector.fit(history)

    def detect(self, value):
        """Evaluate ``value`` with every member and merge the verdicts.

        Args:
            value: The numeric value to evaluate.

        Returns:
            A DetectionResult with the majority verdict and weighted mean score.
        """
        results = [detector.detect(value) for detector in self.detectors]
        votes = sum(1 for result in results if result.is_anomaly)
        score = float(np.dot(self.weights, [result.score for result in results]))
        return DetectionResult(
            is_anomaly=votes > len(results) / 2,
            score=score,
            severity=self._classify_severity(score),
            value=value,
        )
