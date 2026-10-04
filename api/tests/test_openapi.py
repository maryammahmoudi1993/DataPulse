from rest_framework.test import APIClient


def test_schema_endpoint_returns_200(db):
    response = APIClient().get('/api/schema/')

    assert response.status_code == 200
    assert response['content-type'].startswith('application/vnd.oai.openapi')


def test_swagger_ui_returns_200(db):
    assert APIClient().get('/api/schema/swagger-ui/').status_code == 200


def test_redoc_returns_200(db):
    assert APIClient().get('/api/schema/redoc/').status_code == 200


def test_schema_documents_new_endpoints(db):
    response = APIClient().get('/api/schema/', HTTP_ACCEPT='application/json')

    paths = response.json()['paths']
    assert '/api/integrations/slack/' in paths
    assert '/api/streams/{stream_pk}/alerts/{id}/resolve/' in paths
    assert '/api/invites/{token}/' in paths
