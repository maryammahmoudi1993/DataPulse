from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import UserWorkspace, WorkspaceInvite
from streams.models import Workspace

User = get_user_model()


@pytest.fixture
def invite(db):
    owner = User.objects.create_user('owner', password='x')
    workspace = Workspace.objects.create(name='Acme', slug='acme', owner=owner)
    UserWorkspace.objects.create(user=owner, workspace=workspace, role=UserWorkspace.ROLE_OWNER)
    return WorkspaceInvite.objects.create(
        workspace=workspace, invited_by=owner, email='new@example.com', role=UserWorkspace.ROLE_VIEWER,
    )


def test_get_invite_info_returns_workspace_details(invite):
    response = APIClient().get(f'/api/invites/{invite.token}/')

    assert response.status_code == 200
    assert response.data['workspace_name'] == 'Acme'
    assert response.data['workspace_slug'] == 'acme'
    assert response.data['role'] == UserWorkspace.ROLE_VIEWER
    assert response.data['invited_by'] == 'owner'
    assert response.data['expires_at'] == invite.expires_at.isoformat()


def test_get_invite_info_invalid_token(db):
    assert APIClient().get('/api/invites/not-a-token/').status_code == 404


def test_get_invite_info_expired_token(invite):
    WorkspaceInvite.objects.filter(pk=invite.pk).update(expires_at=timezone.now() - timedelta(hours=1))

    response = APIClient().get(f'/api/invites/{invite.token}/')

    assert response.status_code == 410
    invite.refresh_from_db()
    assert invite.status == WorkspaceInvite.STATUS_EXPIRED


def test_get_invite_info_used_token_is_not_found(invite):
    WorkspaceInvite.objects.filter(pk=invite.pk).update(status=WorkspaceInvite.STATUS_ACCEPTED)

    assert APIClient().get(f'/api/invites/{invite.token}/').status_code == 404


def test_invite_page_flow_info_then_accept(invite):
    guest = User.objects.create_user('guest', password='x')
    client = APIClient()
    client.force_authenticate(guest)

    assert client.get(f'/api/invites/{invite.token}/').status_code == 200
    accepted = client.post(f'/api/invites/{invite.token}/accept/')

    assert accepted.status_code == 200
    assert UserWorkspace.objects.filter(user=guest, workspace=invite.workspace).exists()
    assert client.get(f'/api/invites/{invite.token}/').status_code == 404
