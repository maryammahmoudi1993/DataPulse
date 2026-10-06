import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


def test_x_frame_options_deny(client):
    assert client.get('/health/')['X-Frame-Options'] == 'DENY'


def test_x_content_type_nosniff(client):
    assert client.get('/health/')['X-Content-Type-Options'] == 'nosniff'


def test_referrer_policy_present(client):
    assert client.get('/health/')['Referrer-Policy'] == 'strict-origin-when-cross-origin'


def test_permissions_policy_restricts_browser_apis(client):
    policy = client.get('/health/')['Permissions-Policy']

    assert 'camera=()' in policy and 'geolocation=()' in policy


def test_headers_present_on_error_responses(client):
    response = client.get('/api/streams/')

    assert response.status_code == 401
    assert response['X-Frame-Options'] == 'DENY'


@pytest.mark.django_db
def test_csp_on_html_response(client):
    response = client.get('/admin/login/')

    assert 'text/html' in response['Content-Type']
    assert "frame-ancestors 'none'" in response['Content-Security-Policy']


def test_no_csp_on_json_response(client):
    assert 'Content-Security-Policy' not in client.get('/health/')


def test_api_docs_csp_allows_cdn_assets(client):
    response = client.get('/api/schema/swagger-ui/')

    assert 'https://cdn.jsdelivr.net' in response['Content-Security-Policy']
