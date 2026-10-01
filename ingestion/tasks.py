import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from streams.models import Stream

from datapulse.metrics import datapoints_ingested
from detection.pipeline import detect_and_alert
from realtime.publisher import publish_stream_event
from ingestion.models import DataPoint
from sources.factory import get_source_adapter

logger = logging.getLogger(__name__)


@shared_task
def poll_all_active_streams():
    stream_ids = list(
        Stream.objects.filter(status=Stream.STATUS_ACTIVE).values_list('id', flat=True)
    )
    for stream_id in stream_ids:
        poll_stream.delay(stream_id)
    return len(stream_ids)


@shared_task
def poll_stream(stream_id):
    try:
        stream = Stream.objects.get(pk=stream_id)
    except Stream.DoesNotExist:
        return None

    if stream.status != Stream.STATUS_ACTIVE:
        return None

    adapter = get_source_adapter(stream)
    value = adapter.read()

    point = DataPoint.objects.create(
        stream=stream,
        timestamp=timezone.now(),
        value=value,
    )

    datapoints_ingested.labels(stream_id=stream.id).inc()

    publish_stream_event(stream.id, {
        'type': 'datapoint',
        'id': point.id,
        'value': point.value,
        'timestamp': point.timestamp.isoformat(),
    })

    detect_and_alert.delay(point.id)

    return point.id


@shared_task
def cleanup_old_datapoints():
    """Delete data points older than each stream's ``retention_days``.

    Streams with ``retention_days=None`` are skipped.

    Returns:
        Dict with ``streams_processed`` and ``total_deleted``.
    """
    streams = list(Stream.objects.filter(retention_days__isnull=False))
    total = 0
    for stream in streams:
        cutoff = timezone.now() - timedelta(days=stream.retention_days)
        deleted, _ = DataPoint.objects.filter(stream=stream, timestamp__lt=cutoff).delete()
        if deleted:
            total += deleted
            logger.info('Retention cleanup', extra={'stream_id': stream.id, 'deleted': deleted})
    return {'streams_processed': len(streams), 'total_deleted': total}
