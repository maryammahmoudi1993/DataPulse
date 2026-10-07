from datetime import timedelta

import pytest
from django.utils import timezone

from ingestion.models import DataPoint
from streams.models import Stream, StreamRollup, Workspace
from streams.tasks import compute_daily_rollups, compute_hourly_rollups


@pytest.fixture
def stream(db):
    workspace = Workspace.objects.create(name='W', slug='w')
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


def _last_hour_start():
    return (timezone.now() - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)


def _seed_last_hour(stream, values):
    start = _last_hour_start()
    DataPoint.objects.bulk_create([
        DataPoint(stream=stream, timestamp=start + timedelta(minutes=i), value=v)
        for i, v in enumerate(values)
    ])


def test_compute_hourly_rollups_creates_row(stream):
    _seed_last_hour(stream, [float(i) for i in range(10)])

    result = compute_hourly_rollups()

    rollup = StreamRollup.objects.get(stream=stream)
    assert result == {'created': 1, 'updated': 0}
    assert rollup.period == StreamRollup.PERIOD_HOURLY
    assert rollup.bucket_ts == _last_hour_start()
    assert rollup.count == 10
    assert rollup.mean == pytest.approx(4.5)


def test_rollup_is_idempotent(stream):
    _seed_last_hour(stream, [1.0, 2.0, 3.0])

    compute_hourly_rollups()
    second = compute_hourly_rollups()

    assert StreamRollup.objects.filter(stream=stream).count() == 1
    assert second == {'created': 0, 'updated': 1}


def test_rollup_skips_empty_bucket(stream):
    assert compute_hourly_rollups() == {'created': 0, 'updated': 0}
    assert not StreamRollup.objects.exists()


def test_rollup_p95_within_range(stream):
    _seed_last_hour(stream, [3.0, 1.0, 4.0, 1.0, 5.0, 9.0, 2.0, 6.0])

    compute_hourly_rollups()

    rollup = StreamRollup.objects.get(stream=stream)
    assert rollup.min_val <= rollup.p50 <= rollup.p95 <= rollup.p99 <= rollup.max_val


def test_daily_rollup_pools_hourly_rows(stream):
    day_start = (timezone.now() - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    for hour, mean in enumerate([10.0, 20.0]):
        StreamRollup.objects.create(
            stream=stream, period=StreamRollup.PERIOD_HOURLY, bucket_ts=day_start + timedelta(hours=hour),
            count=10, mean=mean, std=1.0, min_val=mean - 2, max_val=mean + 2,
            p50=mean, p95=mean + 1, p99=mean + 2, alert_count=1,
        )

    compute_daily_rollups()

    daily = StreamRollup.objects.get(stream=stream, period=StreamRollup.PERIOD_DAILY)
    assert daily.count == 20
    assert daily.mean == pytest.approx(15.0)
    assert daily.std == pytest.approx((1.0 + 25.0) ** 0.5)
    assert (daily.min_val, daily.max_val, daily.alert_count) == (8.0, 22.0, 2)
