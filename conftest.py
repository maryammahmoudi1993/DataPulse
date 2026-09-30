import pytest


@pytest.fixture(autouse=True)
def in_memory_channel_layer(settings):
    """Keep tests independent of a running Redis server."""
    settings.CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
