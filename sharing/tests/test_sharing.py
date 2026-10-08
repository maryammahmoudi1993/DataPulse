from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from alerts.models import Alert
from ingestion.models import DataPoint
from sharing.models import DashboardShare
from sharing.service import create_share
from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='x')


@pytest.fixture
def stream(owner):
    workspace = Workspace.objects.create(name='W', slug='w', owner=owner)
    return Stream.objects.create(workspace=workspace, name='Temp', source_type=Stream.SOURCE_SIMULATOR)


@pytest.fixture
def client(owner):
    api = APIClient()
    api.force_authenticate(owner)
    return api


@pytest.fixture
def share(stream, owner):
    return create_share(stream, owner)


def _public(share_or_token):
    token = getattr(share_or_token, 'token', share_or_token)
    return APIClient().get(f'/api/share/{token}/')


def test_create_share_link(client, stream):
    response = client.post('/api/shares/', {'stream': stream.id, 'days': 7}, format='json')

    assert response.status_code == 201
    assert response.data['share_url'].endswith(f'/share/{response.data["token"]}')
    share = DashboardShare.objects.get(pk=response.data['id'])
    assert share.title == 'Temp — live view'
    assert timedelta(days=6) < share.expires_at - timezone.now() <= timedelta(days=7)


def test_create_share_rejects_foreign_stream_and_bad_days(client, stream):
    other_owner = User.objects.create_user('other', password='x')
    other = Workspace.objects.create(name='O', slug='o', owner=other_owner)
    foreign = Stream.objects.create(workspace=other, name='F', source_type=Stream.SOURCE_SIMULATOR)

    assert client.post('/api/shares/', {'stream': foreign.id}, format='json').status_code == 404
    assert client.post('/api/shares/', {'stream': stream.id, 'days': 'abc'}, format='json').status_code == 400
    assert client.post('/api/shares/', {'stream': stream.id, 'days': 0}, format='json').status_code == 400


def test_public_share_returns_data_without_auth(share, stream):
    now = timezone.now()
    for i in range(3):
        DataPoint.objects.create(stream=stream, timestamp=now + timedelta(seconds=i), value=float(i))

    response = _public(share)

    assert response.status_code == 200
    assert response.data['stream_name'] == 'Temp'
    assert [p['value'] for p in response.data['points']] == [0.0, 1.0, 2.0]


def test_public_share_respects_max_points(stream, owner):
    share = create_share(stream, owner, max_points=2)
    now = timezone.now()
    for i in range(5):
        DataPoint.objects.create(stream=stream, timestamp=now + timedelta(seconds=i), value=float(i))

    assert [p['value'] for p in _public(share).data['points']] == [3.0, 4.0]


def test_expired_share_returns_410(share):
    share.expires_at = timezone.now() - timedelta(seconds=1)
    share.save(update_fields=['expires_at'])

    assert _public(share).status_code == 410


def test_revoked_share_returns_404(share):
    share.is_active = False
    share.save(update_fields=['is_active'])

    assert _public(share).status_code == 404


def test_unknown_token_returns_404(db):
    assert _public('does-not-exist').status_code == 404


def test_view_count_increments(share):
    _public(share)
    _public(share)

    share.refresh_from_db()
    assert share.view_count == 2


def test_revoke_share_via_delete(client, share):
    response = client.delete(f'/api/shares/{share.id}/')

    assert response.status_code == 204
    share.refresh_from_db()
    assert share.is_active is False
    assert _public(share).status_code == 404


def test_share_scoped_to_workspace(share):
    intruder = User.objects.create_user('intruder', password='x')
    api = APIClient()
    api.force_authenticate(intruder)

    assert api.delete(f'/api/shares/{share.id}/').status_code == 404
    assert api.get('/api/shares/').data == []
    share.refresh_from_db()
    assert share.is_active is True


def test_patch_cannot_move_share_to_another_stream(client, share, stream):
    other = Stream.objects.create(workspace=stream.workspace, name='Other', source_type=Stream.SOURCE_SIMULATOR)

    client.patch(f'/api/shares/{share.id}/', {'stream': other.id, 'title': 'New'}, format='json')

    share.refresh_from_db()
    assert (share.stream, share.title) == (stream, 'New')


def test_share_returns_open_alerts_only(share, stream):
    def alert(status):
        return Alert.objects.create(
            stream=stream, timestamp=timezone.now(), value=1.0, anomaly_score=4.2,
            severity=Alert.SEVERITY_HIGH, detector_type='ZSCORE', status=status,
        )
    alert(Alert.STATUS_OPEN)
    alert(Alert.STATUS_ACKNOWLEDGED)
    alert(Alert.STATUS_RESOLVED)

    response = _public(share)

    assert len(response.data['open_alerts']) == 1
    assert response.data['open_alerts'][0]['severity'] == 'HIGH'
