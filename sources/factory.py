from streams.models import Stream

from sources.adapters.csv_adapter import CSVAdapter
from sources.adapters.simulator import SimulatorAdapter

_ADAPTERS = {
    Stream.SOURCE_SIMULATOR: SimulatorAdapter,
    Stream.SOURCE_CSV: CSVAdapter,
}


def get_source_adapter(stream):
    adapter_class = _ADAPTERS.get(stream.source_type)
    if adapter_class is None:
        raise ValueError(f'No source adapter registered for source type: {stream.source_type}')
    return adapter_class(stream)
