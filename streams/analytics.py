from datetime import timedelta

import numpy as np
from django.db.models import Count
from django.utils import timezone

from alerts.models import Alert
from ingestion.models import DataPoint

FLAT_SLOPE_THRESHOLD = 0.02
MIN_TREND_SAMPLES = 10


def moving_average(stream, window=20, last_n=200):
    """Return the newest ``last_n`` points, oldest first, with a rolling mean.

    Args:
        stream: The Stream to read.
        window: Number of points in the rolling window.
        last_n: Number of points to return.

    Returns:
        List of dicts with ``timestamp``, ``value`` and ``ma``.
    """
    points = list(
        DataPoint.objects
        .filter(stream=stream)
        .order_by('-timestamp', '-id')
        .values('timestamp', 'value')[:last_n]
    )
    points.reverse()
    values = [p['value'] for p in points]
    result = []
    for i, point in enumerate(points):
        start = max(0, i - window + 1)
        result.append({
            'timestamp': point['timestamp'].isoformat(),
            'value': point['value'],
            'ma': round(float(np.mean(values[start:i + 1])), 4),
        })
    return result


def trend_direction(stream, last_n=60):
    """Fit a line to the newest ``last_n`` values.

    Returns:
        Dict with ``direction`` ('up', 'down', 'flat' or 'unknown'), ``slope``,
        ``r2`` and ``samples``. Fewer than 10 points yield 'unknown'.
    """
    values = list(
        DataPoint.objects
        .filter(stream=stream)
        .order_by('-timestamp', '-id')
        .values_list('value', flat=True)[:last_n]
    )
    if len(values) < MIN_TREND_SAMPLES:
        return {'direction': 'unknown', 'slope': 0.0, 'r2': 0.0, 'samples': len(values)}

    y = np.array(values[::-1], dtype=float)
    x = np.arange(len(y), dtype=float)
    coeffs = np.polyfit(x, y, 1)
    slope = float(coeffs[0])
    ss_res = float(np.sum((y - np.polyval(coeffs, x)) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    normalised = abs(slope) / (float(np.std(y)) or 1.0)
    if normalised < FLAT_SLOPE_THRESHOLD:
        direction = 'flat'
    else:
        direction = 'up' if slope > 0 else 'down'

    return {
        'direction': direction,
        'slope': round(slope, 6),
        'r2': round(r2, 4),
        'samples': len(y),
    }


def alert_rate(stream, hours=24):
    """Return alert counts per severity for the last ``hours`` hours."""
    since = timezone.now() - timedelta(hours=hours)
    counts = {severity: 0 for severity, _ in Alert.SEVERITY_CHOICES}
    rows = (
        Alert.objects.filter(stream=stream, created_at__gte=since)
        .values('severity').annotate(n=Count('id'))
    )
    for row in rows:
        counts[row['severity']] = row['n']
    return {
        'period_hours': hours,
        'total': sum(counts.values()),
        'by_severity': counts,
    }
