from datetime import timedelta

import pytest
from django.utils import timezone

from ingestion.models import DataPoint
from ingestion.tasks import cleanup_old_datapoints
from streams.models import Stream, Workspace

pytestmark = pytest.mark.django_db


@pytest.fixture
def workspace():
    return Workspace.objects.create(name='Acme', slug='acme')


def make_stream(workspace, retention_days, name='Sensor'):
    return Stream.objects.create(
        workspace=workspace, name=name, source_type=Stream.SOURCE_SIMULATOR, retention_days=retention_days,
    )


def add_points(stream, count, age):
    when = timezone.now() - age
    for i in range(count):
        DataPoint.objects.create(stream=stream, timestamp=when, value=float(i))


def test_cleanup_deletes_old_points(workspace):
    stream = make_stream(workspace, retention_days=7)
    add_points(stream, 10, timedelta(days=10))

    result = cleanup_old_datapoints()

    assert DataPoint.objects.filter(stream=stream).count() == 0
    assert result == {'streams_processed': 1, 'total_deleted': 10}


def test_cleanup_keeps_recent_points(workspace):
    stream = make_stream(workspace, retention_days=7)
    add_points(stream, 5, timedelta(days=1))
    add_points(stream, 3, timedelta(days=30))

    cleanup_old_datapoints()

    assert DataPoint.objects.filter(stream=stream).count() == 5


def test_cleanup_skips_null_retention(workspace):
    stream = make_stream(workspace, retention_days=None)
    add_points(stream, 4, timedelta(days=365))

    result = cleanup_old_datapoints()

    assert DataPoint.objects.filter(stream=stream).count() == 4
    assert result == {'streams_processed': 0, 'total_deleted': 0}


def test_cleanup_only_touches_streams_with_retention(workspace):
    expiring = make_stream(workspace, retention_days=1, name='A')
    forever = make_stream(workspace, retention_days=None, name='B')
    add_points(expiring, 2, timedelta(days=5))
    add_points(forever, 2, timedelta(days=5))

    cleanup_old_datapoints()

    assert DataPoint.objects.filter(stream=expiring).count() == 0
    assert DataPoint.objects.filter(stream=forever).count() == 2
