from dataclasses import dataclass


@dataclass
class DetectionResult:
    is_anomaly: bool
    score: float
    severity: str
    value: float


class BaseDetector:
    SEVERITY_LOW = 'LOW'
    SEVERITY_MEDIUM = 'MEDIUM'
    SEVERITY_HIGH = 'HIGH'
    SEVERITY_CRITICAL = 'CRITICAL'

    def __init__(self, config=None):
        self.config = config or {}

    def fit(self, history):
        """Train the detector on a list of historical numeric values."""
        raise NotImplementedError('Detectors must implement fit()')

    def detect(self, value):
        """Evaluate a single value and return a DetectionResult."""
        raise NotImplementedError('Detectors must implement detect()')

    def _classify_severity(self, score):
        if score >= 4:
            return self.SEVERITY_CRITICAL
        if score >= 3:
            return self.SEVERITY_HIGH
        if score >= 2:
            return self.SEVERITY_MEDIUM
        return self.SEVERITY_LOW
