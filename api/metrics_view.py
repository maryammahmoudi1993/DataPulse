from django.http import HttpResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from datapulse.metrics import active_streams
from streams.models import Stream


def metrics_view(request):
    """Expose Prometheus metrics, refreshing the active-streams gauge first.

    The endpoint is unauthenticated and meant to be scraped from a private network.
    """
    active_streams.set(Stream.objects.filter(status=Stream.STATUS_ACTIVE).count())
    return HttpResponse(generate_latest(), content_type=CONTENT_TYPE_LATEST)
