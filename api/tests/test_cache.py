import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from alerts.models import Alert
from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='x')


@pytest.fixture
def workspace(owner):
    return Workspace.objects.create(name='W', slug='w', owner=owner)


@pytest.fixture
def stream(workspace):
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


@pytest.fixture
def client(owner):
    api = APIClient()
    api.force_authenticate(owner)
    return api


def make_alert(stream, severity='HIGH'):
    return Alert.objects.create(
        stream=stream, timestamp=timezone.now(), value=1.0, anomaly_score=4.0,
        severity=severity, detector_type='ZSCORE',
    )


def count_queries(fn, table):
    """Run ``fn`` and return how many captured queries touched ``table``."""
    with CaptureQueriesContext(connection) as ctx:
        fn()
    return sum(1 for q in ctx.captured_queries if table in q['sql'])


def test_stream_list_cached_after_first_request(client, stream):
    first = count_queries(lambda: client.get('/api/streams/'), 'streams_stream')
    second = count_queries(lambda: client.get('/api/streams/'), 'streams_stream')

    assert first >= 1
    assert second == 0


def test_stream_list_cache_invalidated_on_create(client, workspace, stream):
    client.get('/api/streams/')

    response = client.post('/api/streams/', {
        'workspace': workspace.id, 'name': 'New', 'source_type': 'SIMULATOR',
    }, format='json')
    assert response.status_code == 201

    listing = []
    queries = count_queries(lambda: listing.append(client.get('/api/streams/')), 'streams_stream')
    assert queries >= 1
    assert {s['name'] for s in listing[0].data} == {'S', 'New'}


def test_stream_list_cache_invalidated_for_other_members(client, workspace, stream):
    member = User.objects.create_user('member', password='x')
    workspace.members.add(member)
    other = APIClient()
    other.force_authenticate(member)
    assert [s['status'] for s in other.get('/api/streams/').data] == ['ACTIVE']

    client.post(f'/api/streams/{stream.id}/pause/')

    assert [s['status'] for s in other.get('/api/streams/').data] == ['PAUSED']


def test_alert_list_cached_after_first_request(client, stream):
    make_alert(stream)
    url = f'/api/streams/{stream.id}/alerts/'

    first = count_queries(lambda: client.get(url), 'alerts_alert')
    second = count_queries(lambda: client.get(url), 'alerts_alert')

    assert first >= 1
    assert second == 0


def test_alert_list_invalidated_after_acknowledge(client, stream):
    alert = make_alert(stream)
    url = f'/api/streams/{stream.id}/alerts/'
    assert client.get(url).data[0]['status'] == 'OPEN'

    assert client.post(f'{url}{alert.id}/acknowledge/').status_code == 200

    listing = []
    queries = count_queries(lambda: listing.append(client.get(url)), 'alerts_alert')
    assert queries >= 1
    assert listing[0].data[0]['status'] == 'ACKNOWLEDGED'


def test_alert_list_invalidated_when_new_alert_created(client, stream):
    from alerts.services import create_alert
    from detection.base import DetectionResult
    from ingestion.models import DataPoint

    url = f'/api/streams/{stream.id}/alerts/'
    assert client.get(url).data == []

    point = DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=9.0)
    create_alert(stream, point, DetectionResult(is_anomaly=True, score=5.0, severity='HIGH', value=9.0))

    assert len(client.get(url).data) == 1


def test_alert_list_cache_does_not_leak_to_outsiders(client, stream):
    make_alert(stream)
    url = f'/api/streams/{stream.id}/alerts/'
    assert len(client.get(url).data) == 1  # warm the cache as the owner

    outsider = APIClient()
    outsider.force_authenticate(User.objects.create_user('outsider', password='x'))

    assert outsider.get(url).data == []


def test_alert_list_cache_is_per_filter(client, stream):
    make_alert(stream, severity='HIGH')
    make_alert(stream, severity='LOW')
    url = f'/api/streams/{stream.id}/alerts/'

    assert len(client.get(url).data) == 2
    assert [a['severity'] for a in client.get(url, {'severity': 'high'}).data] == ['HIGH']


def test_cache_miss_returns_correct_data(client, stream):
    alert = make_alert(stream)

    streams = client.get('/api/streams/').data
    alerts = client.get(f'/api/streams/{stream.id}/alerts/').data

    assert [s['id'] for s in streams] == [stream.id]
    assert [a['id'] for a in alerts] == [alert.id]
