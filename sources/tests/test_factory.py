import pytest

from streams.models import Stream, Workspace

from sources.adapters.simulator import SimulatorAdapter
from sources.factory import get_source_adapter


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name='Acme Corp', slug='acme-corp')


@pytest.mark.django_db
def test_get_source_adapter_simulator(workspace):
    stream = Stream.objects.create(
        workspace=workspace,
        name='Sensor',
        source_type=Stream.SOURCE_SIMULATOR,
    )

    adapter = get_source_adapter(stream)

    assert isinstance(adapter, SimulatorAdapter)


@pytest.mark.django_db
def test_get_source_adapter_unknown_raises(workspace):
    stream = Stream.objects.create(
        workspace=workspace,
        name='Sensor',
        source_type=Stream.SOURCE_HTTP,
    )

    with pytest.raises(ValueError):
        get_source_adapter(stream)
