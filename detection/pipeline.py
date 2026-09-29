from celery import shared_task

from detection.factory import get_detector


@shared_task
def detect_and_alert(point_id):
    from ingestion.models import DataPoint

    try:
        point = DataPoint.objects.select_related('stream').get(pk=point_id)
    except DataPoint.DoesNotExist:
        return None

    stream = point.stream
    history_qs = stream.data_points.exclude(pk=point.pk).order_by('-timestamp')[:200]
    history = [dp.value for dp in reversed(list(history_qs))]

    detector = get_detector(stream)
    detector.fit(history)
    result = detector.detect(point.value)

    if result.is_anomaly:
        point.metadata = {
            **point.metadata,
            'anomaly': True,
            'score': result.score,
            'severity': result.severity,
        }
        point.save(update_fields=['metadata'])

    return {
        'is_anomaly': result.is_anomaly,
        'score': result.score,
        'severity': result.severity,
    }
