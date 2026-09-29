class BaseSourceAdapter:
    """Base interface for pulling a single reading from a stream's data source."""

    def __init__(self, stream):
        self.stream = stream
        self.config = stream.source_config or {}

    def read(self):
        """Return a single numeric reading for this stream.

        Subclasses must override this method.
        """
        raise NotImplementedError('Source adapters must implement read()')
