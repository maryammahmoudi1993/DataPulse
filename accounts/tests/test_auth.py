import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from accounts.models import UserWorkspace
from streams.models import Workspace

User = get_user_model()

REGISTER = {'username': 'ada', 'password': 'S3cure-pass!', 'workspace': 'acme'}


@pytest.fixture
def client():
    return APIClient()


def test_register_creates_user_and_workspace(client, db):
    response = client.post('/api/auth/register/', REGISTER, format='json')

    assert response.status_code == 201
    assert response.data['access'] and response.data['refresh']
    user = User.objects.get(username='ada')
    workspace = Workspace.objects.get(slug='acme')
    membership = UserWorkspace.objects.get(user=user, workspace=workspace)
    assert membership.role == UserWorkspace.ROLE_OWNER
    assert workspace.owner == user


def test_register_duplicate_workspace_slug(client, db):
    client.post('/api/auth/register/', REGISTER, format='json')

    response = client.post('/api/auth/register/', {**REGISTER, 'username': 'bob'}, format='json')

    assert response.status_code == 400
    assert 'workspace' in response.data


def test_login_returns_tokens(client, db):
    User.objects.create_user('ada', password='S3cure-pass!')

    response = client.post('/api/auth/token/', {'username': 'ada', 'password': 'S3cure-pass!'}, format='json')

    assert response.status_code == 200
    assert response.data['access'] and response.data['refresh']


def test_login_invalid_credentials(client, db):
    User.objects.create_user('ada', password='S3cure-pass!')

    response = client.post('/api/auth/token/', {'username': 'ada', 'password': 'wrong'}, format='json')

    assert response.status_code == 401


def test_me_requires_auth(client, db):
    assert client.get('/api/auth/me/').status_code == 401


def test_me_returns_profile_with_workspaces(client, db):
    tokens = client.post('/api/auth/register/', REGISTER, format='json').data

    client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
    response = client.get('/api/auth/me/')

    assert response.status_code == 200
    assert response.data['username'] == 'ada'
    assert response.data['workspaces'][0]['slug'] == 'acme'
    assert response.data['workspaces'][0]['role'] == 'OWNER'


def test_logout_blacklists_token(client, db):
    tokens = client.post('/api/auth/register/', REGISTER, format='json').data
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')

    response = client.post('/api/auth/logout/', {'refresh': tokens['refresh']}, format='json')

    assert response.status_code == 204
    reuse = client.post('/api/auth/token/refresh/', {'refresh': tokens['refresh']}, format='json')
    assert reuse.status_code == 401
