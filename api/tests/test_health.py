from unittest import mock

import redis
from django.db.utils import OperationalError
from rest_framework.test import APIClient


def _ready_response(redis_ok=True):
    ping = mock.Mock() if redis_ok else mock.Mock(side_effect=redis.ConnectionError('down'))
    with mock.patch('api.health.redis.from_url', return_value=mock.Mock(ping=ping)):
        return APIClient().get('/readiness/')


def test_health_returns_200(db):
    response = APIClient().get('/health/')

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_readiness_returns_200_when_db_and_redis_ok(db):
    response = _ready_response()

    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_readiness_db_field_present(db):
    assert _ready_response().json()['db'] == 'ok'


def test_readiness_redis_field_present(db):
    assert _ready_response().json()['redis'] == 'ok'


def test_readiness_503_when_redis_down(db):
    response = _ready_response(redis_ok=False)

    assert response.status_code == 503
    assert response.json()['redis'] == 'error'
    assert response.json()['status'] == 'degraded'


def test_readiness_503_when_db_down(db):
    with mock.patch('api.health.connection.ensure_connection', side_effect=OperationalError('down')):
        response = _ready_response()

    assert response.status_code == 503
    assert response.json()['db'] == 'error'
