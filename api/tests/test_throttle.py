import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from api.throttles import WorkspaceRateThrottle
from api.views import StreamViewSet
from streams.models import Workspace

User = get_user_model()


@pytest.mark.django_db
def test_anon_throttle_enforced():
    client = APIClient()
    payload = {'username': 'nobody', 'password': 'wrong'}

    codes = [client.post('/api/auth/token/', payload, format='json').status_code for _ in range(21)]

    assert codes[:20] == [401] * 20
    assert codes[20] == 429


def test_workspace_write_throttle_present():
    view = StreamViewSet()

    for action in ('create', 'update', 'partial_update', 'destroy'):
        view.action = action
        assert any(isinstance(t, WorkspaceRateThrottle) for t in view.get_throttles())

    view.action = 'list'
    assert not any(isinstance(t, WorkspaceRateThrottle) for t in view.get_throttles())


@pytest.mark.django_db
def test_workspace_write_throttle_blocks_excess_writes(monkeypatch):
    monkeypatch.setitem(WorkspaceRateThrottle.THROTTLE_RATES, 'workspace', '2/min')
    user = User.objects.create_user(username='maryam', password='testpass123')
    workspace = Workspace.objects.create(name='Acme', slug='acme', owner=user)
    client = APIClient()
    client.force_authenticate(user=user)
    payload = {'workspace': workspace.id, 'name': 'S', 'source_type': 'SIMULATOR'}

    codes = [client.post('/api/streams/', payload, format='json').status_code for _ in range(3)]

    assert codes == [201, 201, 429]
