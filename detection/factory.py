from streams.models import Stream

from detection.detectors.zscore import ZScoreDetector

_DETECTORS = {
    Stream.DETECTOR_ZSCORE: ZScoreDetector,
}


def get_detector(stream):
    detector_class = _DETECTORS.get(stream.detector_type)
    if detector_class is None:
        raise ValueError(f'No detector registered for detector type: {stream.detector_type}')
    return detector_class(stream.detector_config)
