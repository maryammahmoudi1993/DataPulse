from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from annotations.models import StreamAnnotation
from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='x')


@pytest.fixture
def stream(owner):
    workspace = Workspace.objects.create(name='W', slug='w', owner=owner)
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


@pytest.fixture
def client(owner):
    api = APIClient()
    api.force_authenticate(owner)
    return api


def _url(stream, suffix=''):
    return f'/api/streams/{stream.id}/annotations/{suffix}'


def _make(stream, owner, label='Deploy', offset_minutes=0, **kwargs):
    return StreamAnnotation.objects.create(
        stream=stream, created_by=owner, label=label,
        timestamp=timezone.now() + timedelta(minutes=offset_minutes), **kwargs,
    )


def test_create_event_annotation(client, stream, owner):
    when = timezone.now().isoformat()

    response = client.post(_url(stream), {'label': 'Deploy v2', 'timestamp': when, 'color': 'red'}, format='json')

    assert response.status_code == 201
    annotation = StreamAnnotation.objects.get(pk=response.data['id'])
    assert (annotation.stream, annotation.created_by, annotation.annotation_type) == (stream, owner, 'EVENT')
    assert response.data['created_by_username'] == 'owner'


def test_create_ignores_stream_in_body(client, stream):
    other = Stream.objects.create(workspace=stream.workspace, name='Other', source_type=Stream.SOURCE_SIMULATOR)

    response = client.post(_url(stream), {
        'stream': other.id, 'label': 'x', 'timestamp': timezone.now().isoformat(),
    }, format='json')

    assert StreamAnnotation.objects.get(pk=response.data['id']).stream == stream


def test_create_region_annotation_requires_end_timestamp(client, stream):
    response = client.post(_url(stream), {
        'label': 'Outage', 'annotation_type': 'REGION', 'timestamp': timezone.now().isoformat(),
    }, format='json')

    assert response.status_code == 400
    assert 'end_timestamp' in response.data


def test_region_end_before_start_returns_400(client, stream):
    start = timezone.now()

    response = client.post(_url(stream), {
        'label': 'Outage', 'annotation_type': 'REGION',
        'timestamp': start.isoformat(), 'end_timestamp': (start - timedelta(hours=1)).isoformat(),
    }, format='json')

    assert response.status_code == 400


def test_create_region_annotation(client, stream):
    start = timezone.now()

    response = client.post(_url(stream), {
        'label': 'Outage', 'annotation_type': 'REGION',
        'timestamp': start.isoformat(), 'end_timestamp': (start + timedelta(hours=1)).isoformat(),
    }, format='json')

    assert response.status_code == 201
    assert response.data['end_timestamp'] is not None


def test_list_annotations_scoped_to_stream(client, stream):
    intruder = User.objects.create_user('intruder', password='x')
    _make(stream, stream.workspace.owner)
    other_client = APIClient()
    other_client.force_authenticate(intruder)

    assert other_client.get(_url(stream)).data == []
    assert other_client.post(_url(stream), {
        'label': 'x', 'timestamp': timezone.now().isoformat(),
    }, format='json').status_code == 404
    assert len(client.get(_url(stream)).data) == 1


def test_filter_annotations_by_time_range(client, stream, owner):
    _make(stream, owner, 'early', offset_minutes=-120)
    _make(stream, owner, 'middle', offset_minutes=0)
    _make(stream, owner, 'late', offset_minutes=120)
    after = (timezone.now() - timedelta(minutes=60)).isoformat()
    before = (timezone.now() + timedelta(minutes=60)).isoformat()

    response = client.get(_url(stream), {'after': after, 'before': before})

    assert [a['label'] for a in response.data] == ['middle']


def test_filter_rejects_invalid_datetime(client, stream):
    assert client.get(_url(stream), {'after': 'yesterday'}).status_code == 400


def test_update_annotation_label(client, stream, owner):
    annotation = _make(stream, owner)

    response = client.patch(_url(stream, f'{annotation.id}/'), {'label': 'Renamed'}, format='json')

    assert response.status_code == 200
    annotation.refresh_from_db()
    assert annotation.label == 'Renamed'


def test_delete_annotation(client, stream, owner):
    annotation = _make(stream, owner)

    response = client.delete(_url(stream, f'{annotation.id}/'))

    assert response.status_code == 204
    assert not StreamAnnotation.objects.filter(pk=annotation.pk).exists()
