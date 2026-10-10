import asyncio
import json
from unittest import mock

import pytest
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from rest_framework_simplejwt.tokens import AccessToken
from strawberry.channels.testing import GraphQLWebsocketCommunicator

from alerts.models import Alert
from annotations.models import StreamAnnotation
from accounts.models import UserWorkspace
from api_keys.models import APIKey
from ingestion.models import DataPoint
from realtime.publisher import stream_group_name
from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def owner(db):
    return User.objects.create_user('owner', password='x')


@pytest.fixture
def workspace(owner):
    return Workspace.objects.create(name='W', slug='w', owner=owner)


@pytest.fixture
def stream(workspace):
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


@pytest.fixture
def alert(stream):
    return Alert.objects.create(
        stream=stream, timestamp=timezone.now(), value=9.0, anomaly_score=4.2,
        severity=Alert.SEVERITY_HIGH, detector_type='ZSCORE',
    )


def bearer(user):
    return f'Bearer {AccessToken.for_user(user)}'


def gql(query, auth=None, variables=None):
    headers = {'HTTP_AUTHORIZATION': auth} if auth else {}
    response = Client().post(
        '/graphql/', data=json.dumps({'query': query, 'variables': variables or {}}),
        content_type='application/json', **headers,
    )
    return response.json()


def error_code(result):
    return result['errors'][0]['extensions']['code']


# --- queries -------------------------------------------------------------

def test_anonymous_query_is_rejected(stream):
    result = gql('{ streams { id } }')

    assert error_code(result) == 'UNAUTHENTICATED'


def test_invalid_token_is_rejected(stream):
    result = gql('{ streams { id } }', auth='Bearer garbage')

    assert error_code(result) == 'UNAUTHENTICATED'


def test_member_lists_streams_with_nested_fields(owner, stream, alert):
    DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=1.5)

    result = gql('{ streams { id name status dataPoints(limit: 5) { value } alerts { severity status } } }',
                 auth=bearer(owner))

    assert 'errors' not in result
    [row] = result['data']['streams']
    assert row['id'] == stream.id
    assert row['dataPoints'] == [{'value': 1.5}]
    assert row['alerts'] == [{'severity': 'HIGH', 'status': 'OPEN'}]


def test_outsider_sees_nothing(stream, alert):
    stranger = User.objects.create_user('stranger', password='x')

    result = gql('{ streams { id } alerts { id } stream(id: %d) { id } }' % stream.id, auth=bearer(stranger))

    assert result['data'] == {'streams': [], 'alerts': [], 'stream': None}


def test_alert_filters(owner, stream, alert):
    result = gql('query($s: Severity) { alerts(severity: $s) { id } }', auth=bearer(owner),
                 variables={'s': 'LOW'})

    assert result['data']['alerts'] == []


def test_limit_is_clamped(owner, stream):
    DataPoint.objects.bulk_create(
        [DataPoint(stream=stream, timestamp=timezone.now(), value=i) for i in range(210)],
    )

    result = gql('{ stream(id: %d) { dataPoints(limit: 100000) { id } } }' % stream.id, auth=bearer(owner))

    assert len(result['data']['stream']['dataPoints']) == 200


def test_query_depth_is_limited(owner):
    nested = '{ workspaces { streams { alerts { id } } } }'
    deep = 'query { ' + 'workspaces { streams { ' * 6 + 'id' + ' } }' * 6 + ' }'

    assert 'errors' not in gql(nested, auth=bearer(owner))
    assert 'errors' in gql(deep, auth=bearer(owner))


# --- API keys ------------------------------------------------------------

def test_api_key_scopes_gate_queries(owner, workspace, stream, alert):
    _, raw = APIKey.create(workspace, owner, 'k', ['read:streams'])

    ok = gql('{ streams { id } }', auth=f'Api-Key {raw}')
    denied = gql('{ alerts { id } }', auth=f'Api-Key {raw}')

    assert [s['id'] for s in ok['data']['streams']] == [stream.id]
    assert error_code(denied) == 'FORBIDDEN'


def test_api_key_is_confined_to_its_workspace(owner, workspace, stream):
    other = Workspace.objects.create(name='O', slug='o', owner=owner)
    Stream.objects.create(workspace=other, name='Other', source_type=Stream.SOURCE_SIMULATOR)
    _, raw = APIKey.create(workspace, owner, 'k', ['read:streams'])

    result = gql('{ streams { id } }', auth=f'Api-Key {raw}')

    assert [s['id'] for s in result['data']['streams']] == [stream.id]


def test_api_key_cannot_mutate(owner, workspace, alert):
    _, raw = APIKey.create(workspace, owner, 'k', ['read:streams', 'read:alerts'])

    result = gql('mutation { acknowledgeAlert(id: %d) { id } }' % alert.id, auth=f'Api-Key {raw}')

    assert error_code(result) == 'FORBIDDEN'
    alert.refresh_from_db()
    assert alert.status == Alert.STATUS_OPEN


def test_api_key_can_ingest_with_write_scope(owner, workspace, stream):
    _, raw = APIKey.create(workspace, owner, 'k', ['write:datapoints'])

    with mock.patch('graphql_api.schema.detect_and_alert') as detect:
        result = gql('mutation { ingestDataPoint(streamId: %d, value: 3.5) { value } }' % stream.id,
                     auth=f'Api-Key {raw}')

    assert result['data']['ingestDataPoint']['value'] == 3.5
    detect.delay.assert_called_once()
    assert DataPoint.objects.filter(stream=stream).count() == 1


def test_revoked_api_key_is_rejected(owner, workspace, stream):
    key, raw = APIKey.create(workspace, owner, 'k', ['read:streams'])
    APIKey.objects.filter(pk=key.pk).update(is_active=False)

    assert error_code(gql('{ streams { id } }', auth=f'Api-Key {raw}')) == 'UNAUTHENTICATED'


# --- mutations -----------------------------------------------------------

def test_acknowledge_and_resolve_alert(owner, alert):
    ack = gql('mutation { acknowledgeAlert(id: %d) { status } }' % alert.id, auth=bearer(owner))
    res = gql('mutation { resolveAlert(id: %d) { status } }' % alert.id, auth=bearer(owner))
    again = gql('mutation { resolveAlert(id: %d) { status } }' % alert.id, auth=bearer(owner))

    assert ack['data']['acknowledgeAlert']['status'] == 'ACKNOWLEDGED'
    assert res['data']['resolveAlert']['status'] == 'RESOLVED'
    assert error_code(again) == 'BAD_INPUT'
    alert.refresh_from_db()
    assert alert.acknowledged_by == owner


def test_outsider_cannot_acknowledge(alert):
    stranger = User.objects.create_user('stranger', password='x')

    result = gql('mutation { acknowledgeAlert(id: %d) { id } }' % alert.id, auth=bearer(stranger))

    assert error_code(result) == 'NOT_FOUND'


def test_create_stream_and_toggle_status(owner, workspace):
    created = gql(
        'mutation($i: CreateStreamInput!) { createStream(input: $i) { id name status sourceType } }',
        auth=bearer(owner), variables={'i': {'workspaceId': workspace.id, 'name': ' New '}},
    )
    stream_id = created['data']['createStream']['id']
    paused = gql('mutation { setStreamStatus(id: %d, status: PAUSED) { status } }' % stream_id,
                 auth=bearer(owner))

    assert created['data']['createStream']['name'] == 'New'
    assert paused['data']['setStreamStatus']['status'] == 'PAUSED'


def test_create_stream_in_foreign_workspace_fails(workspace):
    stranger = User.objects.create_user('stranger', password='x')

    result = gql('mutation($i: CreateStreamInput!) { createStream(input: $i) { id } }',
                 auth=bearer(stranger), variables={'i': {'workspaceId': workspace.id, 'name': 'x'}})

    assert error_code(result) == 'NOT_FOUND'


def test_ingest_rejects_non_finite(owner, stream):
    result = gql('mutation($v: Float!) { ingestDataPoint(streamId: %d, value: $v) { id } }' % stream.id,
                 auth=bearer(owner), variables={'v': 1e999})

    assert 'errors' in result


def test_annotation_create_validates_and_deletes(owner, stream):
    ts = timezone.now().isoformat()
    query = 'mutation($i: CreateAnnotationInput!) { createAnnotation(input: $i) { id kind } }'

    region_without_end = gql(query, auth=bearer(owner), variables={
        'i': {'streamId': stream.id, 'label': 'x', 'timestamp': ts, 'kind': 'REGION'}})
    ok = gql(query, auth=bearer(owner), variables={
        'i': {'streamId': stream.id, 'label': 'deploy', 'timestamp': ts}})
    annotation_id = ok['data']['createAnnotation']['id']
    deleted = gql('mutation { deleteAnnotation(id: %d) }' % annotation_id, auth=bearer(owner))

    assert error_code(region_without_end) == 'BAD_INPUT'
    assert deleted['data']['deleteAnnotation'] is True
    assert not StreamAnnotation.objects.exists()


# --- subscriptions -------------------------------------------------------

SUBSCRIPTION = 'subscription($s: Int!) { streamEvents(streamId: $s) { type value severity alertId } }'


def _run_subscription(stream, auth, events):
    """Subscribe, publish ``events`` once registered, return one result per event (or the first error)."""
    from datapulse.asgi import application

    async def scenario():
        params = {'Authorization': auth} if auth else {}
        async with GraphQLWebsocketCommunicator(application, '/graphql/', connection_params=params) as client:
            results = client.subscribe(query=SUBSCRIPTION, variables={'s': stream.id})
            # The subscribe message is only sent when iteration starts.
            pending = asyncio.ensure_future(results.__anext__())
            await asyncio.sleep(0.3)  # let the subscription join the channel group
            layer = get_channel_layer()
            for payload in events:
                await layer.group_send(stream_group_name(stream.id), {'type': 'stream.event', 'payload': payload})
            out = [await pending]
            for _ in events[1:]:
                out.append(await results.__anext__())
            return out

    return async_to_sync(scenario)()


@pytest.mark.django_db(transaction=True)
def test_subscription_streams_events(owner, stream):
    events = [
        {'type': 'datapoint', 'id': 1, 'value': 2.5, 'timestamp': 't'},
        {'type': 'alert', 'alert_id': 7, 'severity': 'HIGH', 'score': 4.0, 'value': 9.0, 'timestamp': 't'},
    ]

    first, second = _run_subscription(stream, bearer(owner), events)

    assert first.data['streamEvents'] == {'type': 'datapoint', 'value': 2.5, 'severity': None, 'alertId': None}
    assert second.data['streamEvents']['alertId'] == 7


@pytest.mark.django_db(transaction=True)
def test_subscription_denies_unauthenticated(stream):
    [result] = _run_subscription(stream, None, [])

    assert result.errors[0].extensions['code'] == 'FORBIDDEN'


@pytest.mark.django_db(transaction=True)
def test_subscription_denies_foreign_user(stream):
    stranger = User.objects.create_user('stranger', password='x')

    [result] = _run_subscription(stream, bearer(stranger), [])

    assert result.errors[0].extensions['code'] == 'FORBIDDEN'


# --- roles ---------------------------------------------------------------

@pytest.fixture
def viewer(workspace):
    user = User.objects.create_user('viewer', password='x')
    UserWorkspace.objects.create(user=user, workspace=workspace, role=UserWorkspace.ROLE_VIEWER)
    return user


@pytest.fixture
def member(workspace):
    user = User.objects.create_user('member', password='x')
    UserWorkspace.objects.create(user=user, workspace=workspace, role=UserWorkspace.ROLE_MEMBER)
    return user


def test_viewer_cannot_acknowledge_alert(viewer, alert):
    result = gql('mutation { acknowledgeAlert(id: %d) { id } }' % alert.id, auth=bearer(viewer))

    assert error_code(result) == 'FORBIDDEN'
    alert.refresh_from_db()
    assert alert.status == Alert.STATUS_OPEN


def test_member_can_acknowledge_alert(member, alert):
    result = gql('mutation { acknowledgeAlert(id: %d) { status } }' % alert.id, auth=bearer(member))

    assert result['data']['acknowledgeAlert']['status'] == 'ACKNOWLEDGED'


def test_viewer_can_still_read(viewer, stream):
    result = gql('{ streams { id } }', auth=bearer(viewer))

    assert [s['id'] for s in result['data']['streams']] == [stream.id]


def test_viewer_cannot_use_any_write_mutation(viewer, workspace, stream, alert):
    ts = timezone.now().isoformat()
    annotation = StreamAnnotation.objects.create(stream=stream, label='a', timestamp=timezone.now())
    attempts = [
        ('mutation { resolveAlert(id: %d) { id } }' % alert.id, None),
        ('mutation { setStreamStatus(id: %d, status: PAUSED) { id } }' % stream.id, None),
        ('mutation { ingestDataPoint(streamId: %d, value: 1.0) { id } }' % stream.id, None),
        ('mutation { deleteAnnotation(id: %d) }' % annotation.id, None),
        ('mutation($i: CreateAnnotationInput!) { createAnnotation(input: $i) { id } }',
         {'i': {'streamId': stream.id, 'label': 'x', 'timestamp': ts}}),
        ('mutation($i: CreateStreamInput!) { createStream(input: $i) { id } }',
         {'i': {'workspaceId': workspace.id, 'name': 'x'}}),
    ]

    for query, variables in attempts:
        assert error_code(gql(query, auth=bearer(viewer), variables=variables)) == 'FORBIDDEN', query

    stream.refresh_from_db()
    assert stream.status == Stream.STATUS_ACTIVE
    assert StreamAnnotation.objects.filter(pk=annotation.pk).exists()


def test_legacy_m2m_member_can_write(workspace, alert):
    legacy = User.objects.create_user('legacy', password='x')
    workspace.members.add(legacy)

    result = gql('mutation { resolveAlert(id: %d) { status } }' % alert.id, auth=bearer(legacy))

    assert result['data']['resolveAlert']['status'] == 'RESOLVED'
