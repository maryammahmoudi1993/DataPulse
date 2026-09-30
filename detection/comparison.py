import copy
import logging

from detection.factory import get_detector
from ingestion.models import DataPoint

logger = logging.getLogger(__name__)

MIN_POINTS = 10
MIN_WINDOW = 5
HISTORY_LIMIT = 200
SAMPLE_LIMIT = 10


def _detector_for(stream, detector_type):
    """Build a detector of ``detector_type`` using the stream's config."""
    variant = copy.copy(stream)
    variant.detector_type = detector_type
    return get_detector(variant)


def compare_detectors(stream, type_a, type_b, last_n=300):
    """Run two detectors over the same historical window and compare them.

    Each point after the first ``MIN_WINDOW`` is evaluated by both detectors
    against the preceding history, mirroring how the live pipeline works.

    Args:
        stream: Stream whose stored data points are replayed.
        type_a: Detector type of the first detector.
        type_b: Detector type of the second detector.
        last_n: Number of most recent points to replay.

    Returns:
        Dict with agreement statistics and samples of divergent points, or
        ``{'error': ...}`` when the stream has too little data.
    """
    values = list(
        DataPoint.objects
        .filter(stream=stream)
        .order_by('-timestamp', '-id')
        .values_list('value', flat=True)[:last_n]
    )
    if len(values) < MIN_POINTS:
        return {'error': f'Insufficient data (need >= {MIN_POINTS} points)'}
    values.reverse()

    detector_a = _detector_for(stream, type_a)
    detector_b = _detector_for(stream, type_b)

    only_a, only_b = [], []
    both = neither = 0

    for i in range(MIN_WINDOW, len(values)):
        history = values[max(0, i - HISTORY_LIMIT):i]
        value = values[i]
        detector_a.fit(history)
        detector_b.fit(history)
        result_a = detector_a.detect(value)
        result_b = detector_b.detect(value)

        if result_a.is_anomaly and result_b.is_anomaly:
            both += 1
        elif not result_a.is_anomaly and not result_b.is_anomaly:
            neither += 1
        elif result_a.is_anomaly:
            only_a.append({'index': i, 'value': value, 'score_a': result_a.score})
        else:
            only_b.append({'index': i, 'value': value, 'score_b': result_b.score})

    total = len(values) - MIN_WINDOW
    agreement = round((both + neither) / total * 100, 1) if total else 0.0

    logger.info('Detector comparison complete', extra={
        'stream_id': stream.id,
        'detector_a': type_a,
        'detector_b': type_b,
        'agreement_pct': agreement,
    })

    return {
        'total_evaluated': total,
        'agreement_pct': agreement,
        'both_anomaly': both,
        'neither_anomaly': neither,
        'only_a_count': len(only_a),
        'only_b_count': len(only_b),
        'only_a_samples': only_a[:SAMPLE_LIMIT],
        'only_b_samples': only_b[:SAMPLE_LIMIT],
        'detector_a': type_a,
        'detector_b': type_b,
    }
