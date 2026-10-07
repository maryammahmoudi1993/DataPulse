import logging
from datetime import timedelta

import numpy as np
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def compute_hourly_rollups():
    """Compute hourly StreamRollup rows for the two most recent full hours.

    Idempotent: rows are keyed on (stream, period, bucket_ts) and rewritten
    with ``update_or_create``, so re-running after a worker crash is safe.

    Returns:
        Dict with the number of rollup rows ``created`` and ``updated``.
    """
    from alerts.models import Alert
    from ingestion.models import DataPoint
    from streams.models import Stream, StreamRollup

    now = timezone.now()
    created = 0
    updated = 0

    for stream in Stream.objects.all():
        for hours_ago in (1, 2):
            bucket_start = (now - timedelta(hours=hours_ago)).replace(minute=0, second=0, microsecond=0)
            bucket_end = bucket_start + timedelta(hours=1)

            values = list(
                DataPoint.objects
                .filter(stream=stream, timestamp__gte=bucket_start, timestamp__lt=bucket_end)
                .values_list('value', flat=True)
            )
            if not values:
                continue

            arr = np.array(values, dtype=float)
            alert_count = Alert.objects.filter(
                stream=stream, timestamp__gte=bucket_start, timestamp__lt=bucket_end,
            ).count()

            _, was_created = StreamRollup.objects.update_or_create(
                stream=stream,
                period=StreamRollup.PERIOD_HOURLY,
                bucket_ts=bucket_start,
                defaults={
                    'count': len(arr),
                    'mean': float(np.mean(arr)),
                    'std': float(np.std(arr)),
                    'min_val': float(np.min(arr)),
                    'max_val': float(np.max(arr)),
                    'p50': float(np.percentile(arr, 50)),
                    'p95': float(np.percentile(arr, 95)),
                    'p99': float(np.percentile(arr, 99)),
                    'alert_count': alert_count,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

    logger.info('Hourly rollups complete', extra={'created': created, 'updated': updated})
    return {'created': created, 'updated': updated}


@shared_task
def compute_daily_rollups():
    """Compute daily StreamRollup rows for yesterday from the hourly rows.

    The mean and standard deviation are exact (pooled from the hourly
    moments). The median is the count-weighted mean of hourly medians, and
    p95/p99 are the largest hourly values, which makes them upper bounds.

    Returns:
        Dict with the number of rollup rows ``created`` and ``updated``.
    """
    from streams.models import Stream, StreamRollup

    day_start = (timezone.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    created = 0
    updated = 0

    for stream in Stream.objects.all():
        rows = list(StreamRollup.objects.filter(
            stream=stream,
            period=StreamRollup.PERIOD_HOURLY,
            bucket_ts__gte=day_start,
            bucket_ts__lt=day_end,
        ))
        total = sum(r.count for r in rows)
        if total == 0:
            continue

        mean = sum(r.count * r.mean for r in rows) / total
        variance = sum(r.count * (r.std ** 2 + (r.mean - mean) ** 2) for r in rows) / total

        _, was_created = StreamRollup.objects.update_or_create(
            stream=stream,
            period=StreamRollup.PERIOD_DAILY,
            bucket_ts=day_start,
            defaults={
                'count': total,
                'mean': mean,
                'std': float(np.sqrt(variance)),
                'min_val': min(r.min_val for r in rows),
                'max_val': max(r.max_val for r in rows),
                'p50': sum(r.count * r.p50 for r in rows) / total,
                'p95': max(r.p95 for r in rows),
                'p99': max(r.p99 for r in rows),
                'alert_count': sum(r.alert_count for r in rows),
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    logger.info('Daily rollups complete', extra={'created': created, 'updated': updated})
    return {'created': created, 'updated': updated}
