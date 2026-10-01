import logging
import time

from celery import shared_task

from datapulse.metrics import anomalies_detected, detection_latency
from detection.factory import get_detector

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 200


@shared_task
def detect_and_alert(point_id):
    """Run the stream's detector on a data point and raise an alert if needed.

    Args:
        point_id: Primary key of the DataPoint to evaluate.

    Returns:
        Dict with ``is_anomaly``, ``score`` and ``severity``, or None when
        the point no longer exists.
    """
    from alerts.services import create_alert
    from ingestion.models import DataPoint

    try:
        point = DataPoint.objects.select_related('stream').get(pk=point_id)
    except DataPoint.DoesNotExist:
        return None

    stream = point.stream
    history_qs = stream.data_points.exclude(pk=point.pk).order_by('-timestamp', '-id')[:HISTORY_LIMIT]
    history = [dp.value for dp in reversed(list(history_qs))]

    detector = get_detector(stream)
    detector.fit(history)
    started = time.perf_counter()
    result = detector.detect(point.value)
    detection_latency.labels(detector_type=stream.detector_type).observe(time.perf_counter() - started)
    if result.is_anomaly:
        anomalies_detected.labels(severity=result.severity, detector_type=stream.detector_type).inc()

    logger.info('Detection complete', extra={
        'stream_id': stream.id,
        'score': result.score,
        'is_anomaly': result.is_anomaly,
    })

    if result.is_anomaly:
        point.metadata = {
            **point.metadata,
            'anomaly': True,
            'score': result.score,
            'severity': result.severity,
        }
        point.save(update_fields=['metadata'])
        create_alert(stream, point, result)

    return {
        'is_anomaly': result.is_anomaly,
        'score': result.score,
        'severity': result.severity,
    }
