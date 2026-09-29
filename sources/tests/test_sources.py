import pytest

from streams.models import Stream, Workspace

from sources.adapters.csv_adapter import CSVAdapter
from sources.adapters.simulator import SimulatorAdapter


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name='Acme Corp', slug='acme-corp')


def _make_stream(workspace, source_type, source_config=None):
    return Stream.objects.create(
        workspace=workspace,
        name='Sensor',
        source_type=source_type,
        source_config=source_config or {},
    )


@pytest.mark.django_db
def test_simulator_returns_float(workspace):
    stream = _make_stream(workspace, Stream.SOURCE_SIMULATOR, {'baseline': 50.0, 'noise_std': 1.0})
    adapter = SimulatorAdapter(stream)

    value = adapter.read()

    assert isinstance(value, float)


@pytest.mark.django_db
def test_simulator_spike_injection(workspace):
    stream = _make_stream(
        workspace,
        Stream.SOURCE_SIMULATOR,
        {
            'baseline': 0.0,
            'noise_std': 0.1,
            'spike_probability': 1.0,
            'spike_magnitude': 20.0,
        },
    )
    adapter = SimulatorAdapter(stream)

    value = adapter.read()

    assert abs(value) > 5.0


@pytest.mark.django_db
def test_csv_adapter_reads_column(workspace, tmp_path):
    csv_file = tmp_path / 'readings.csv'
    csv_file.write_text('value\n1.5\n2.5\n3.5\n')

    stream = _make_stream(workspace, Stream.SOURCE_CSV, {'file_path': str(csv_file)})
    adapter = CSVAdapter(stream)

    assert adapter.read() == 1.5
    assert adapter.read() == 2.5


@pytest.mark.django_db
def test_csv_adapter_loops(workspace, tmp_path):
    csv_file = tmp_path / 'readings.csv'
    csv_file.write_text('value\n1.0\n2.0\n')

    stream = _make_stream(workspace, Stream.SOURCE_CSV, {'file_path': str(csv_file)})
    adapter = CSVAdapter(stream)

    values = [adapter.read() for _ in range(4)]

    assert values == [1.0, 2.0, 1.0, 2.0]
