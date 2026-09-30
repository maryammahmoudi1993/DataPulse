import logging

import redis
from django.conf import settings
from django.db import connection
from django.db.utils import Error as DatabaseError
from django.http import JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


def health(request):
    """Liveness probe: returns 200 whenever the process is serving requests."""
    return JsonResponse({'status': 'ok', 'ts': timezone.now().isoformat()})


def readiness(request):
    """Readiness probe: verifies database and Redis connectivity.

    Returns:
        200 when every dependency answers, 503 otherwise.
    """
    checks = {}

    try:
        connection.ensure_connection()
        checks['db'] = 'ok'
    except DatabaseError as exc:
        checks['db'] = 'error'
        logger.error('Readiness DB check failed', extra={'exc': str(exc)})

    try:
        redis.from_url(settings.REDIS_URL, socket_connect_timeout=2).ping()
        checks['redis'] = 'ok'
    except (redis.RedisError, OSError) as exc:
        checks['redis'] = 'error'
        logger.error('Readiness Redis check failed', extra={'exc': str(exc)})

    all_ok = all(v == 'ok' for v in checks.values())
    payload = {'status': 'ok' if all_ok else 'degraded', **checks, 'ts': timezone.now().isoformat()}
    return JsonResponse(payload, status=200 if all_ok else 503)
