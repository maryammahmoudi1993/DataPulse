from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from streams.models import Stream, Workspace

from ingestion.models import DataPoint
from ingestion.tasks import poll_all_active_streams, poll_stream


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name='Acme Corp', slug='acme-corp')


@pytest.fixture
def active_stream(workspace):
    return Stream.objects.create(
        workspace=workspace,
        name='Temperature Sensor',
        source_type=Stream.SOURCE_SIMULATOR,
        status=Stream.STATUS_ACTIVE,
    )


@pytest.mark.django_db
def test_datapoint_creation(active_stream):
    point = DataPoint.objects.create(
        stream=active_stream,
        timestamp=timezone.now(),
        value=42.5,
    )

    assert point.pk is not None
    assert point.value == 42.5
    assert point.metadata == {}


def test_datapoint_index():
    index_fields = [tuple(index.fields) for index in DataPoint._meta.indexes]

    assert ('stream', 'timestamp') in index_fields


@pytest.mark.django_db
def test_poll_stream_task(active_stream):
    fake_adapter = MagicMock()
    fake_adapter.read.return_value = 12.3

    with patch('ingestion.tasks.get_source_adapter', return_value=fake_adapter) as mock_factory:
        result = poll_stream(active_stream.id)

    mock_factory.assert_called_once()
    assert DataPoint.objects.filter(stream=active_stream, value=12.3).exists()
    assert result is not None


@pytest.mark.django_db
def test_poll_stream_skips_paused(workspace):
    paused_stream = Stream.objects.create(
        workspace=workspace,
        name='Paused Sensor',
        source_type=Stream.SOURCE_SIMULATOR,
        status=Stream.STATUS_PAUSED,
    )

    with patch('ingestion.tasks.get_source_adapter') as mock_factory:
        result = poll_stream(paused_stream.id)

    mock_factory.assert_not_called()
    assert result is None
    assert not DataPoint.objects.filter(stream=paused_stream).exists()


@pytest.mark.django_db
def test_poll_all_active_streams_dispatches_only_active(workspace, active_stream):
    Stream.objects.create(
        workspace=workspace,
        name='Paused Sensor',
        source_type=Stream.SOURCE_SIMULATOR,
        status=Stream.STATUS_PAUSED,
    )

    with patch('ingestion.tasks.poll_stream') as mock_poll_stream:
        dispatched = poll_all_active_streams()

    assert dispatched == 1
    mock_poll_stream.delay.assert_called_once_with(active_stream.id)
