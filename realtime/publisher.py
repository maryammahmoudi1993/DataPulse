import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def stream_group_name(stream_id):
    """Return the channel-layer group name for a stream."""
    return f'stream_{stream_id}'


def publish_stream_event(stream_id, payload):
    """Broadcast an event to every WebSocket client watching a stream.

    Delivery is best effort: a broker outage must never break ingestion or
    detection, so connection errors are logged and swallowed.

    Args:
        stream_id: Primary key of the stream.
        payload: JSON-serialisable dict; must contain a ``type`` key.

    Returns:
        True when the event was handed to the channel layer, else False.
    """
    layer = get_channel_layer()
    if layer is None:
        return False
    try:
        async_to_sync(layer.group_send)(
            stream_group_name(stream_id),
            {'type': 'stream.event', 'payload': payload},
        )
    except (OSError, ConnectionError) as e:
        logger.warning('Could not publish event for stream %s: %s', stream_id, e)
        return False
    return True
