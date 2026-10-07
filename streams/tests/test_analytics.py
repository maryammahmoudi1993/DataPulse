from datetime import timedelta

import pytest
from django.utils import timezone

from alerts.models import Alert
from ingestion.models import DataPoint
from streams.analytics import alert_rate, moving_average, trend_direction
from streams.models import Stream, Workspace


@pytest.fixture
def stream(db):
    workspace = Workspace.objects.create(name='W', slug='w')
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


def _seed(stream, values):
    start = timezone.now() - timedelta(seconds=len(values))
    DataPoint.objects.bulk_create([
        DataPoint(stream=stream, timestamp=start + timedelta(seconds=i), value=v)
        for i, v in enumerate(values)
    ])


def _alert(stream, severity):
    return Alert.objects.create(
        stream=stream, timestamp=timezone.now(), value=1.0, anomaly_score=3.0,
        severity=severity, detector_type='ZSCORE',
    )


def test_moving_average_returns_correct_length(stream):
    _seed(stream, [float(i) for i in range(50)])

    rows = moving_average(stream, window=10)

    assert len(rows) == 50
    assert all('ma' in row for row in rows)


def test_moving_average_first_window_is_single_value(stream):
    _seed(stream, [5.0, 7.0, 9.0])

    rows = moving_average(stream, window=3)

    assert rows[0]['ma'] == rows[0]['value'] == 5.0
    assert rows[2]['ma'] == pytest.approx(7.0)


def test_trend_direction_rising(stream):
    _seed(stream, [float(i) for i in range(40)])

    result = trend_direction(stream)

    assert result['direction'] == 'up'
    assert result['r2'] == pytest.approx(1.0)


def test_trend_direction_flat(stream):
    _seed(stream, [10.0] * 40)

    assert trend_direction(stream)['direction'] == 'flat'


def test_trend_returns_unknown_on_short_history(stream):
    _seed(stream, [1.0, 2.0, 3.0])

    assert trend_direction(stream)['direction'] == 'unknown'


def test_alert_rate_counts_by_severity(stream):
    _alert(stream, 'HIGH')
    _alert(stream, 'HIGH')
    _alert(stream, 'LOW')

    result = alert_rate(stream, hours=24)

    assert result['total'] == 3
    assert result['by_severity']['HIGH'] == 2
    assert result['by_severity']['LOW'] == 1
    assert result['by_severity']['CRITICAL'] == 0
