from datetime import timedelta

import pytest
from django.db.utils import IntegrityError
from django.utils import timezone

from streams.models import Stream, Workspace


@pytest.mark.django_db
def test_workspace_creation():
    workspace = Workspace.objects.create(name='Acme Corp', slug='acme-corp')

    assert workspace.pk is not None
    assert workspace.name == 'Acme Corp'
    assert workspace.slug == 'acme-corp'


@pytest.mark.django_db
def test_stream_defaults():
    workspace = Workspace.objects.create(name='Acme Corp', slug='acme-corp')
    stream = Stream.objects.create(
        workspace=workspace,
        name='Temperature Sensor',
        source_type=Stream.SOURCE_SIMULATOR,
    )

    assert stream.sampling_interval == 5
    assert stream.detector_type == Stream.DETECTOR_ZSCORE
    assert stream.status == Stream.STATUS_ACTIVE
    assert stream.source_config == {}
    assert stream.detector_config == {}


@pytest.mark.django_db
def test_stream_str():
    workspace = Workspace.objects.create(name='Acme Corp', slug='acme-corp')
    stream = Stream.objects.create(
        workspace=workspace,
        name='Temperature Sensor',
        source_type=Stream.SOURCE_SIMULATOR,
    )

    assert str(stream) == 'acme-corp/Temperature Sensor'


@pytest.mark.django_db
def test_stream_requires_workspace():
    with pytest.raises(IntegrityError):
        Stream.objects.create(
            name='Orphan Stream',
            source_type=Stream.SOURCE_SIMULATOR,
        )


@pytest.mark.django_db
def test_stream_ordering():
    workspace = Workspace.objects.create(name='Acme Corp', slug='acme-corp')
    first = Stream.objects.create(workspace=workspace, name='First', source_type=Stream.SOURCE_SIMULATOR)
    second = Stream.objects.create(workspace=workspace, name='Second', source_type=Stream.SOURCE_SIMULATOR)

    Stream.objects.filter(pk=first.pk).update(created_at=timezone.now() - timedelta(minutes=1))

    streams = list(Stream.objects.all())

    assert streams[0] == second
    assert streams[1] == first
