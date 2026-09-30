import datetime

from django.conf import settings
from django.utils import timezone

from alerts.models import Alert
from realtime.publisher import publish_stream_event


def create_alert(stream, point, result):
    """Persist an alert for an anomalous point unless it is a duplicate.

    An alert is suppressed when the stream already raised one of the same
    severity inside the deduplication window.

    Args:
        stream: The Stream the point belongs to.
        point: The anomalous DataPoint.
        result: The DetectionResult produced by the detector.

    Returns:
        The new Alert, or None when it was suppressed as a duplicate.
    """
    window = datetime.timedelta(minutes=settings.ALERT_DEDUP_WINDOW_MINUTES)
    recent = Alert.objects.filter(
        stream=stream,
        severity=result.severity,
        created_at__gte=timezone.now() - window,
    )
    if recent.exists():
        return None

    alert = Alert.objects.create(
        stream=stream,
        data_point=point,
        timestamp=point.timestamp,
        value=result.value,
        anomaly_score=result.score,
        severity=result.severity,
        detector_type=stream.detector_type,
    )

    publish_stream_event(stream.id, {
        'type': 'alert',
        'alert_id': alert.id,
        'severity': alert.severity,
        'score': alert.anomaly_score,
        'value': alert.value,
        'timestamp': alert.timestamp.isoformat(),
    })

    from alerts.tasks import dispatch_webhooks
    dispatch_webhooks.delay(alert.id)
    return alert
