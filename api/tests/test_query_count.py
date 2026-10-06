"""Regression guards against N+1 queries.

Each test asserts an upper bound, not an exact count, so one extra join from
a future feature does not break it; only per-row queries (O(N)) do.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import UserWorkspace
from alerts.models import Alert
from audit.models import AuditEvent
from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='x')


@pytest.fixture
def workspace(owner):
    return Workspace.objects.create(name='W', slug='w', owner=owner)


@pytest.fixture
def client(owner):
    api = APIClient()
    api.force_authenticate(owner)
    return api


def queries_for(client, url):
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url)
    assert response.status_code == 200
    return len(ctx)


def test_stream_list_queries_bounded(client, workspace):
    for total in (1, 5, 20):
        while Stream.objects.count() < total:
            Stream.objects.create(workspace=workspace, name=f's{Stream.objects.count()}',
                                  source_type=Stream.SOURCE_SIMULATOR)
        cache.clear()

        assert queries_for(client, '/api/streams/') <= 4


def test_alert_list_queries_bounded(client, workspace):
    stream = Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)
    url = f'/api/streams/{stream.id}/alerts/'
    for total in (1, 10, 40):
        Alert.objects.bulk_create([
            Alert(stream=stream, timestamp=timezone.now(), value=1.0, anomaly_score=4.0,
                  severity='HIGH', detector_type='ZSCORE')
            for _ in range(total - Alert.objects.count())
        ])
        cache.clear()

        assert queries_for(client, url) <= 3


def test_audit_list_queries_bounded(client, workspace, owner):
    UserWorkspace.objects.create(user=owner, workspace=workspace, role=UserWorkspace.ROLE_OWNER)
    stream = Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)
    other = User.objects.create_user('other', password='x')
    url = f'/api/workspaces/{workspace.id}/audit/'
    for total in (1, 10, 40):
        AuditEvent.objects.bulk_create([
            AuditEvent(workspace=workspace, actor=owner, target_user=other, stream=stream,
                       action='STREAM_CREATED')
            for _ in range(total - AuditEvent.objects.count())
        ])

        assert queries_for(client, url) <= 3


def test_member_list_queries_bounded(client, workspace):
    url = f'/api/workspaces/{workspace.id}/members/'
    for total in (1, 10, 25):
        while UserWorkspace.objects.count() < total:
            user = User.objects.create_user(f'u{UserWorkspace.objects.count()}', password='x')
            UserWorkspace.objects.create(user=user, workspace=workspace)

        assert queries_for(client, url) <= 3
