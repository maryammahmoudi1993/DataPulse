import pytest


@pytest.fixture(autouse=True)
def in_memory_channel_layer(settings):
    """Keep tests independent of a running Redis server."""
    settings.CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Reset DRF throttle counters so request limits never leak between tests."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
