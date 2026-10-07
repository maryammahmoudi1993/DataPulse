import datetime
import logging

from django.conf import settings
from django.utils import timezone

from alerts.models import Alert
from api.cache_keys import invalidate_alert_cache
from datapulse.metrics import alerts_created
from realtime.publisher import publish_stream_event

logger = logging.getLogger(__name__)


def create_alert(stream, point, result, detector_type=None):
    """Persist an alert for an anomalous point unless it is a duplicate.

    An alert is suppressed when the stream already raised one of the same
    severity inside the deduplication window.

    Args:
        stream: The Stream the point belongs to.
        point: The anomalous DataPoint.
        result: The DetectionResult produced by the detector.
        detector_type: Source recorded on the alert; defaults to the stream's detector.

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
        logger.info('Alert suppressed as duplicate', extra={'stream_id': stream.id, 'severity': result.severity})
        return None

    alert = Alert.objects.create(
        stream=stream,
        data_point=point,
        timestamp=point.timestamp,
        value=result.value,
        anomaly_score=result.score,
        severity=result.severity,
        detector_type=detector_type or stream.detector_type,
    )

    alerts_created.labels(severity=alert.severity).inc()
    invalidate_alert_cache(stream.id)

    logger.info('Alert created', extra={
        'stream_id': stream.id,
        'alert_id': alert.id,
        'severity': alert.severity,
    })

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

    from integrations.tasks import dispatch_pagerduty_incident, dispatch_slack_notification
    for task in (dispatch_slack_notification, dispatch_pagerduty_incident):
        try:
            task.delay(alert.id)
        except Exception:
            # A failing notification channel must never block alert creation.
            logger.exception('Notification dispatch failed', extra={'alert_id': alert.id, 'task': task.name})
    return alert
