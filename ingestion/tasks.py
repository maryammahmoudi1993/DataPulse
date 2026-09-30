from celery import shared_task
from django.utils import timezone

from streams.models import Stream

from detection.pipeline import detect_and_alert
from realtime.publisher import publish_stream_event
from ingestion.models import DataPoint
from sources.factory import get_source_adapter


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

    publish_stream_event(stream.id, {
        'type': 'datapoint',
        'id': point.id,
        'value': point.value,
        'timestamp': point.timestamp.isoformat(),
    })

    detect_and_alert.delay(point.id)

    return point.id
