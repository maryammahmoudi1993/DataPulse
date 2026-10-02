import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import UserWorkspace
from audit.models import AuditEvent
from streams.models import Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', email='owner@example.com', password='x')


@pytest.fixture
def workspace(owner):
    ws = Workspace.objects.create(name='W', slug='w', owner=owner)
    UserWorkspace.objects.create(user=owner, workspace=ws, role=UserWorkspace.ROLE_OWNER)
    return ws


@pytest.fixture
def member(workspace):
    user = User.objects.create_user('member', email='member@example.com', password='x')
    UserWorkspace.objects.create(user=user, workspace=workspace, role=UserWorkspace.ROLE_MEMBER)
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def _url(workspace, user_id=None):
    base = f'/api/workspaces/{workspace.id}/members/'
    return base if user_id is None else f'{base}{user_id}/'


def test_list_members_returns_all_workspace_users(workspace, owner, member):
    response = _client(member).get(_url(workspace))

    assert response.status_code == 200
    assert {m['username'] for m in response.data} == {'owner', 'member'}
    assert {m['role'] for m in response.data} == {'OWNER', 'MEMBER'}


def test_list_members_hidden_from_outsiders(workspace):
    outsider = User.objects.create_user('outsider', password='x')

    assert _client(outsider).get(_url(workspace)).status_code == 404


def test_change_role_by_owner_succeeds(workspace, owner, member):
    response = _client(owner).patch(_url(workspace, member.id), {'role': 'VIEWER'}, format='json')

    assert response.status_code == 200
    assert response.data['role'] == 'VIEWER'
    assert UserWorkspace.objects.get(user=member, workspace=workspace).role == 'VIEWER'
    assert AuditEvent.objects.filter(action='MEMBER_ROLE_CHANGED', target_user=member).exists()


def test_change_role_by_non_owner_returns_403(workspace, owner, member):
    response = _client(member).patch(_url(workspace, owner.id), {'role': 'VIEWER'}, format='json')

    assert response.status_code == 403
    assert UserWorkspace.objects.get(user=owner, workspace=workspace).role == 'OWNER'


def test_change_role_rejects_invalid_role_and_unknown_member(workspace, owner, member):
    client = _client(owner)

    assert client.patch(_url(workspace, member.id), {'role': 'GOD'}, format='json').status_code == 400
    assert client.patch(_url(workspace, 9999), {'role': 'VIEWER'}, format='json').status_code == 404
    assert client.patch(_url(workspace, 'abc'), {'role': 'VIEWER'}, format='json').status_code == 404


def test_cannot_demote_self(workspace, owner):
    response = _client(owner).patch(_url(workspace, owner.id), {'role': 'MEMBER'}, format='json')

    assert response.status_code == 400
    assert UserWorkspace.objects.get(user=owner, workspace=workspace).role == 'OWNER'


def test_remove_member_by_owner_succeeds(workspace, owner, member):
    response = _client(owner).delete(_url(workspace, member.id))

    assert response.status_code == 204
    assert not UserWorkspace.objects.filter(user=member, workspace=workspace).exists()
    assert AuditEvent.objects.filter(action='MEMBER_REMOVED', workspace=workspace).exists()


def test_remove_member_by_non_owner_returns_403(workspace, owner, member):
    assert _client(member).delete(_url(workspace, owner.id)).status_code == 403


def test_remove_unknown_member_returns_404(workspace, owner):
    assert _client(owner).delete(_url(workspace, 9999)).status_code == 404


def test_remove_self_returns_400(workspace, owner):
    response = _client(owner).delete(_url(workspace, owner.id))

    assert response.status_code == 400
    assert UserWorkspace.objects.filter(user=owner, workspace=workspace).exists()


def test_remove_last_owner_returns_400(workspace, owner, member):
    UserWorkspace.objects.filter(user=member).update(role=UserWorkspace.ROLE_OWNER)
    assert _client(owner).delete(_url(workspace, member.id)).status_code == 204

    # The sole remaining owner can neither remove nor demote themselves.
    assert _client(owner).delete(_url(workspace, owner.id)).status_code == 400
    assert _client(owner).patch(_url(workspace, owner.id), {'role': 'MEMBER'}, format='json').status_code == 400
    assert UserWorkspace.objects.filter(workspace=workspace, role='OWNER').count() == 1
