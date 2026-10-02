from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.invite_service import accept_invite, create_invite
from accounts.models import UserWorkspace, WorkspaceInvite
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


def test_create_invite_saves_to_db(workspace, owner):
    invite = create_invite(workspace, owner, 'new@example.com', UserWorkspace.ROLE_VIEWER)

    stored = WorkspaceInvite.objects.get(pk=invite.pk)
    assert stored.status == WorkspaceInvite.STATUS_PENDING
    assert stored.role == UserWorkspace.ROLE_VIEWER
    assert stored.email == 'new@example.com'
    assert stored.expires_at > timezone.now()


def test_create_invite_rejects_existing_member(workspace, owner):
    with pytest.raises(ValueError):
        create_invite(workspace, owner, 'owner@example.com', UserWorkspace.ROLE_MEMBER)


def test_create_invite_supersedes_old_pending(workspace, owner):
    first = create_invite(workspace, owner, 'new@example.com', UserWorkspace.ROLE_MEMBER)
    second = create_invite(workspace, owner, 'new@example.com', UserWorkspace.ROLE_MEMBER)
    third = create_invite(workspace, owner, 'new@example.com', UserWorkspace.ROLE_MEMBER)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.status == WorkspaceInvite.STATUS_EXPIRED
    assert second.status == WorkspaceInvite.STATUS_EXPIRED
    assert third.status == WorkspaceInvite.STATUS_PENDING


def test_accept_invite_creates_membership(workspace, owner):
    invite = create_invite(workspace, owner, 'new@example.com', UserWorkspace.ROLE_VIEWER)
    newcomer = User.objects.create_user('newcomer', email='new@example.com', password='x')

    membership = accept_invite(invite.token, newcomer)

    assert membership.role == UserWorkspace.ROLE_VIEWER
    assert UserWorkspace.objects.filter(user=newcomer, workspace=workspace, role='VIEWER').exists()
    invite.refresh_from_db()
    assert invite.status == WorkspaceInvite.STATUS_ACCEPTED
    assert invite.accepted_by == newcomer


def test_accept_invite_expired_token(workspace, owner):
    invite = create_invite(workspace, owner, 'new@example.com', UserWorkspace.ROLE_MEMBER)
    WorkspaceInvite.objects.filter(pk=invite.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    newcomer = User.objects.create_user('newcomer', password='x')

    with pytest.raises(ValueError, match='expired'):
        accept_invite(invite.token, newcomer)

    invite.refresh_from_db()
    assert invite.status == WorkspaceInvite.STATUS_EXPIRED
    assert not UserWorkspace.objects.filter(user=newcomer).exists()


def test_accept_invite_invalid_token(db):
    user = User.objects.create_user('someone', password='x')
    with pytest.raises(ValueError):
        accept_invite('does-not-exist', user)


def test_accept_invite_already_used_token(workspace, owner):
    invite = create_invite(workspace, owner, 'new@example.com', UserWorkspace.ROLE_MEMBER)
    first = User.objects.create_user('first', password='x')
    second = User.objects.create_user('second', password='x')
    accept_invite(invite.token, first)

    with pytest.raises(ValueError):
        accept_invite(invite.token, second)
    assert not UserWorkspace.objects.filter(user=second).exists()


def test_accept_invite_api_endpoint(workspace, owner):
    invite = create_invite(workspace, owner, 'new@example.com', UserWorkspace.ROLE_MEMBER)
    newcomer = User.objects.create_user('newcomer', password='x')
    client = APIClient()
    client.force_authenticate(newcomer)

    response = client.post(f'/api/invites/{invite.token}/accept/')

    assert response.status_code == 200
    assert response.data['workspace_slug'] == 'w'
    assert response.data['role'] == UserWorkspace.ROLE_MEMBER

    again = client.post(f'/api/invites/{invite.token}/accept/')
    assert again.status_code == 400


def test_invite_api_requires_owner(workspace):
    member = User.objects.create_user('member', password='x')
    UserWorkspace.objects.create(user=member, workspace=workspace, role=UserWorkspace.ROLE_MEMBER)
    client = APIClient()
    client.force_authenticate(member)

    response = client.post(
        f'/api/workspaces/{workspace.id}/invites/', {'email': 'x@example.com', 'role': 'OWNER'}, format='json',
    )

    assert response.status_code == 403
    assert not WorkspaceInvite.objects.exists()


def test_invite_api_create_list_revoke(workspace, owner):
    client = APIClient()
    client.force_authenticate(owner)
    base = f'/api/workspaces/{workspace.id}/invites/'

    created = client.post(base, {'email': 'x@example.com', 'role': 'VIEWER'}, format='json')
    assert created.status_code == 201
    assert 'token' not in created.data

    listed = client.get(base)
    assert [i['email'] for i in listed.data] == ['x@example.com']

    assert client.delete(f'{base}{created.data["id"]}/').status_code == 204
    assert client.delete(f'{base}{created.data["id"]}/').status_code == 404
    assert client.get(base).data == []


def test_invite_api_rejects_member_email_and_bad_role(workspace, owner):
    client = APIClient()
    client.force_authenticate(owner)
    base = f'/api/workspaces/{workspace.id}/invites/'

    assert client.post(base, {'email': 'owner@example.com'}, format='json').status_code == 400
    assert client.post(base, {'email': 'y@example.com', 'role': 'GOD'}, format='json').status_code == 400
