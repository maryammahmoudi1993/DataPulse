import asyncio
import datetime
import math
from typing import AsyncGenerator, Optional

import strawberry
from channels.db import database_sync_to_async
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.utils import timezone
from graphql import GraphQLError
from strawberry.extensions import MaxTokensLimiter, QueryDepthLimiter

from alerts.models import Alert
from annotations.models import StreamAnnotation
from api.cache_keys import invalidate_alert_cache
from audit.services import log_event
from datapulse.metrics import datapoints_ingested
from detection.pipeline import detect_and_alert
from ingestion.models import DataPoint
from realtime.publisher import publish_stream_event, stream_group_name
from streams.models import Stream

from graphql_api.guards import require_member_or_above
from graphql_api.types import (
    AlertStatus,
    AlertType,
    AnnotationKind,
    AnnotationType,
    DataPointType,
    DetectorType,
    Severity,
    SourceType,
    StreamEvent,
    StreamStatus,
    StreamType,
    WorkspaceType,
    clamp,
)

MAX_DEPTH = 8
MAX_TOKENS = 2000
EVENT_TYPES = {'datapoint', 'alert'}


def _not_found(what):
    return GraphQLError(f'{what} not found.', extensions={'code': 'NOT_FOUND'})


def _bad_input(message):
    return GraphQLError(message, extensions={'code': 'BAD_INPUT'})


@strawberry.type
class Query:
    @strawberry.field
    def workspaces(self, info: strawberry.Info) -> list[WorkspaceType]:
        principal = info.context.require_scope('read:streams')
        return [WorkspaceType.from_model(w) for w in principal.workspaces()]

    @strawberry.field
    def streams(
        self, info: strawberry.Info, workspace_id: Optional[int] = None,
        status: Optional[StreamStatus] = None, limit: Optional[int] = None,
    ) -> list[StreamType]:
        principal = info.context.require_scope('read:streams')
        qs = Stream.objects.filter(workspace__in=principal.workspaces())
        if workspace_id is not None:
            qs = qs.filter(workspace_id=workspace_id)
        if status:
            qs = qs.filter(status=status.value)
        return [StreamType.from_model(s) for s in qs[:clamp(limit)]]

    @strawberry.field
    def stream(self, info: strawberry.Info, id: int) -> Optional[StreamType]:
        principal = info.context.require_scope('read:streams')
        s = Stream.objects.filter(pk=id, workspace__in=principal.workspaces()).first()
        return StreamType.from_model(s) if s else None

    @strawberry.field
    def alerts(
        self, info: strawberry.Info, stream_id: Optional[int] = None,
        severity: Optional[Severity] = None, status: Optional[AlertStatus] = None,
        limit: Optional[int] = None,
    ) -> list[AlertType]:
        principal = info.context.require_scope('read:alerts')
        qs = Alert.objects.filter(stream__workspace__in=principal.workspaces())
        if stream_id is not None:
            qs = qs.filter(stream_id=stream_id)
        if severity:
            qs = qs.filter(severity=severity.value)
        if status:
            qs = qs.filter(status=status.value)
        return [AlertType.from_model(a) for a in qs[:clamp(limit)]]


@strawberry.input
class CreateStreamInput:
    workspace_id: int
    name: str
    source_type: SourceType = SourceType.HTTP
    detector_type: DetectorType = DetectorType.ZSCORE
    sampling_interval: int = 5


@strawberry.input
class CreateAnnotationInput:
    stream_id: int
    label: str
    timestamp: datetime.datetime
    description: str = ''
    kind: AnnotationKind = AnnotationKind.EVENT
    color: str = 'blue'
    end_timestamp: Optional[datetime.datetime] = None


def _writable_alert(ctx, alert_id):
    principal = ctx.require_user()
    alert = Alert.objects.select_related('stream__workspace').filter(
        pk=alert_id, stream__workspace__in=principal.workspaces(),
    ).first()
    if alert is None:
        raise _not_found('Alert')
    require_member_or_above(principal, alert.stream.workspace_id)
    return principal, alert


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_stream(self, info: strawberry.Info, input: CreateStreamInput) -> StreamType:
        principal = info.context.require_user()
        workspace = principal.workspaces().filter(pk=input.workspace_id).first()
        if workspace is None:
            raise _not_found('Workspace')
        require_member_or_above(principal, workspace.pk)
        if not input.name.strip() or input.sampling_interval < 1:
            raise _bad_input('Invalid name or sampling interval.')
        stream = Stream.objects.create(
            workspace=workspace, name=input.name.strip(), source_type=input.source_type.value,
            detector_type=input.detector_type.value, sampling_interval=input.sampling_interval,
        )
        return StreamType.from_model(stream)

    @strawberry.mutation
    def set_stream_status(self, info: strawberry.Info, id: int, status: StreamStatus) -> StreamType:
        principal = info.context.require_user()
        stream = Stream.objects.filter(pk=id, workspace__in=principal.workspaces()).first()
        if stream is None:
            raise _not_found('Stream')
        require_member_or_above(principal, stream.workspace_id)
        stream.status = status.value
        stream.save(update_fields=['status', 'updated_at'])
        return StreamType.from_model(stream)

    @strawberry.mutation
    def ingest_data_point(self, info: strawberry.Info, stream_id: int, value: float) -> DataPointType:
        principal = info.context.require_scope('write:datapoints')
        stream = Stream.objects.filter(pk=stream_id, workspace__in=principal.workspaces()).first()
        if stream is None:
            raise _not_found('Stream')
        if principal.api_key is None:  # API keys are governed by scope, people by role
            require_member_or_above(principal, stream.workspace_id)
        if not math.isfinite(value):
            raise _bad_input('A finite numeric value is required.')
        point = DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=value)
        datapoints_ingested.labels(stream_id=stream.id).inc()
        publish_stream_event(stream.id, {
            'type': 'datapoint', 'id': point.id, 'value': point.value, 'timestamp': point.timestamp.isoformat(),
        })
        detect_and_alert.delay(point.id)
        return DataPointType.from_model(point)

    @strawberry.mutation
    def acknowledge_alert(self, info: strawberry.Info, id: int) -> AlertType:
        principal, alert = _writable_alert(info.context, id)
        alert.status = Alert.STATUS_ACKNOWLEDGED
        alert.acknowledged_by = principal.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at'])
        invalidate_alert_cache(alert.stream_id)
        log_event(actor=principal.user, workspace=alert.stream.workspace, action='ALERT_ACKNOWLEDGED',
                  stream=alert.stream, metadata={'alert_id': alert.id, 'via': 'graphql'})
        return AlertType.from_model(alert)

    @strawberry.mutation
    def resolve_alert(self, info: strawberry.Info, id: int) -> AlertType:
        principal, alert = _writable_alert(info.context, id)
        if alert.status == Alert.STATUS_RESOLVED:
            raise _bad_input('Alert is already resolved.')
        alert.status = Alert.STATUS_RESOLVED
        alert.save(update_fields=['status'])
        invalidate_alert_cache(alert.stream_id)
        log_event(actor=principal.user, workspace=alert.stream.workspace, action='ALERT_RESOLVED',
                  stream=alert.stream, metadata={'alert_id': alert.id, 'via': 'graphql'})
        return AlertType.from_model(alert)

    @strawberry.mutation
    def create_annotation(self, info: strawberry.Info, input: CreateAnnotationInput) -> AnnotationType:
        principal = info.context.require_user()
        stream = Stream.objects.filter(pk=input.stream_id, workspace__in=principal.workspaces()).first()
        if stream is None:
            raise _not_found('Stream')
        require_member_or_above(principal, stream.workspace_id)
        annotation = StreamAnnotation(
            stream=stream, created_by=principal.user, label=input.label, description=input.description,
            annotation_type=input.kind.value, color=input.color, timestamp=input.timestamp,
            end_timestamp=input.end_timestamp,
        )
        try:
            annotation.full_clean()
        except ValidationError as e:
            raise _bad_input('; '.join(e.messages))
        annotation.save()
        return AnnotationType.from_model(annotation)

    @strawberry.mutation
    def delete_annotation(self, info: strawberry.Info, id: int) -> bool:
        principal = info.context.require_user()
        annotation = StreamAnnotation.objects.select_related('stream').filter(
            pk=id, stream__workspace__in=principal.workspaces(),
        ).first()
        if annotation is None:
            raise _not_found('Annotation')
        require_member_or_above(principal, annotation.stream.workspace_id)
        annotation.delete()
        return True


@database_sync_to_async
def _authorise_stream(ctx, stream_id):
    """Return True when the caller may watch ``stream_id``."""
    principal = ctx.principal
    if not principal.is_authenticated or not principal.has_scope('read:streams'):
        return False
    return Stream.objects.filter(pk=stream_id, workspace__in=principal.workspaces()).exists()


@strawberry.type
class Subscription:
    @strawberry.subscription
    async def stream_events(
        self, info: strawberry.Info, stream_id: int, event_types: Optional[list[str]] = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Live data points and alerts for one stream (same feed as the REST WebSocket)."""
        if not await _authorise_stream(info.context, stream_id):
            raise GraphQLError('Stream not found or not permitted.', extensions={'code': 'FORBIDDEN'})

        wanted = EVENT_TYPES if not event_types else EVENT_TYPES & set(event_types)
        layer = get_channel_layer()
        channel = await layer.new_channel()
        group = stream_group_name(stream_id)
        await layer.group_add(group, channel)
        try:
            while True:
                message = await layer.receive(channel)
                payload = message.get('payload') or {}
                if payload.get('type') not in wanted:
                    continue
                yield StreamEvent(
                    type=payload['type'], id=payload.get('id'), alert_id=payload.get('alert_id'),
                    value=payload.get('value'), score=payload.get('score'),
                    severity=payload.get('severity'), timestamp=payload.get('timestamp'),
                )
        finally:
            await asyncio.shield(layer.group_discard(group, channel))


schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    extensions=[lambda: QueryDepthLimiter(max_depth=MAX_DEPTH), lambda: MaxTokensLimiter(max_token_count=MAX_TOKENS)],
)
