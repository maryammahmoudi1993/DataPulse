from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from ingestion.models import DataPoint
from streams.models import Stream, Workspace

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup():
    user = User.objects.create_user(username='maryam', password='testpass123')
    workspace = Workspace.objects.create(name='Acme', slug='acme', owner=user)
    stream = Stream.objects.create(workspace=workspace, name='Sensor', source_type=Stream.SOURCE_SIMULATOR)
    client = APIClient()
    client.force_authenticate(user=user)
    return client, stream


def add_points(stream, count, start=0):
    base = timezone.now() - timedelta(hours=1)
    return [
        DataPoint.objects.create(stream=stream, timestamp=base + timedelta(seconds=start + i), value=float(i))
        for i in range(count)
    ]


def test_datapoints_endpoint_returns_cursor(setup):
    client, stream = setup
    add_points(stream, 5)

    response = client.get(f'/api/streams/{stream.id}/datapoints/?page_size=2')

    assert response.status_code == 200
    assert len(response.data['results']) == 2
    assert response.data['next'] is not None
    assert response.data['previous'] is None


def test_cursor_pagination_stable_across_writes(setup):
    client, stream = setup
    add_points(stream, 6)
    first = client.get(f'/api/streams/{stream.id}/datapoints/?page_size=2').data
    before = client.get(first['next']).data

    add_points(stream, 1, start=3600)  # newer than everything fetched so far
    after = client.get(first['next']).data

    assert [p['id'] for p in after['results']] == [p['id'] for p in before['results']]


def test_cursor_pages_cover_all_points_newest_first(setup):
    client, stream = setup
    points = add_points(stream, 5)
    seen, url = [], f'/api/streams/{stream.id}/datapoints/?page_size=2'

    while url:
        data = client.get(url).data
        seen += [p['id'] for p in data['results']]
        url = data['next']

    assert seen == [p.id for p in reversed(points)]


def test_legacy_limit_param_returns_plain_list(setup):
    client, stream = setup
    add_points(stream, 5)

    response = client.get(f'/api/streams/{stream.id}/datapoints/?limit=3')

    assert isinstance(response.data, list)
    assert len(response.data) == 3
