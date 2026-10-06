import pytest


@pytest.fixture(autouse=True)
def in_memory_channel_layer(settings):
    """Keep tests independent of a running Redis server."""
    settings.CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}


@pytest.fixture(autouse=True)
def local_memory_cache(settings):
    """Use an in-process cache so tests never depend on a running Redis server."""
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


@pytest.fixture(autouse=True)
def clear_throttle_cache(local_memory_cache):
    """Reset DRF throttle counters and cached responses so state never leaks between tests."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()
