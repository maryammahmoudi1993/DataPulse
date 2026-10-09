import datetime
import enum
from typing import Optional

import strawberry

from alerts.models import Alert
from annotations.models import StreamAnnotation
from ingestion.models import DataPoint
from streams.models import Stream, StreamRollup, Workspace

MAX_PAGE = 200


def clamp(limit, default=50):
    """Bound a client-supplied page size to ``1..MAX_PAGE``."""
    if limit is None:
        return default
    return max(1, min(limit, MAX_PAGE))


def _enum(name, choices):
    """Build a GraphQL enum whose members mirror a Django ``choices`` list."""
    return strawberry.enum(enum.Enum(name, {value: value for value, _ in choices}), name=name)


Severity = _enum('Severity', Alert.SEVERITY_CHOICES)
AlertStatus = _enum('AlertStatus', Alert.STATUS_CHOICES)
StreamStatus = _enum('StreamStatus', Stream.STATUS_CHOICES)
SourceType = _enum('SourceType', Stream.SOURCE_CHOICES)
DetectorType = _enum('DetectorType', Stream.DETECTOR_CHOICES)
AnnotationKind = _enum('AnnotationKind', StreamAnnotation.TYPE_CHOICES)
RollupPeriod = _enum('RollupPeriod', StreamRollup.PERIOD_CHOICES)


@strawberry.type
class DataPointType:
    id: int
    timestamp: datetime.datetime
    value: float

    @classmethod
    def from_model(cls, p: DataPoint):
        return cls(id=p.id, timestamp=p.timestamp, value=p.value)


@strawberry.type
class AlertType:
    id: int
    stream_id: int
    timestamp: datetime.datetime
    value: float
    anomaly_score: float
    severity: Severity
    status: AlertStatus
    detector_type: str
    acknowledged_at: Optional[datetime.datetime]

    @classmethod
    def from_model(cls, a: Alert):
        return cls(
            id=a.id, stream_id=a.stream_id, timestamp=a.timestamp, value=a.value,
            anomaly_score=a.anomaly_score, severity=Severity(a.severity), status=AlertStatus(a.status),
            detector_type=a.detector_type, acknowledged_at=a.acknowledged_at,
        )


@strawberry.type
class AnnotationType:
    id: int
    stream_id: int
    label: str
    description: str
    kind: AnnotationKind
    color: str
    timestamp: datetime.datetime
    end_timestamp: Optional[datetime.datetime]

    @classmethod
    def from_model(cls, a: StreamAnnotation):
        return cls(
            id=a.id, stream_id=a.stream_id, label=a.label, description=a.description,
            kind=AnnotationKind(a.annotation_type), color=a.color, timestamp=a.timestamp,
            end_timestamp=a.end_timestamp,
        )


@strawberry.type
class RollupType:
    period: RollupPeriod
    bucket_ts: datetime.datetime
    count: int
    mean: float
    std: float
    min_val: float
    max_val: float
    p50: float
    p95: float
    p99: float
    alert_count: int

    @classmethod
    def from_model(cls, r: StreamRollup):
        return cls(
            period=RollupPeriod(r.period), bucket_ts=r.bucket_ts, count=r.count, mean=r.mean, std=r.std,
            min_val=r.min_val, max_val=r.max_val, p50=r.p50, p95=r.p95, p99=r.p99, alert_count=r.alert_count,
        )


@strawberry.type
class StreamType:
    id: int
    workspace_id: int
    name: str
    source_type: SourceType
    detector_type: DetectorType
    status: StreamStatus
    sampling_interval: int
    created_at: datetime.datetime

    @classmethod
    def from_model(cls, s: Stream):
        return cls(
            id=s.id, workspace_id=s.workspace_id, name=s.name, source_type=SourceType(s.source_type),
            detector_type=DetectorType(s.detector_type), status=StreamStatus(s.status),
            sampling_interval=s.sampling_interval, created_at=s.created_at,
        )

    @strawberry.field
    def data_points(
        self, info: strawberry.Info, limit: Optional[int] = None,
        since: Optional[datetime.datetime] = None,
    ) -> list[DataPointType]:
        """Most recent data points, newest first."""
        info.context.require_scope('read:streams')
        qs = DataPoint.objects.filter(stream_id=self.id)
        if since:
            qs = qs.filter(timestamp__gte=since)
        return [DataPointType.from_model(p) for p in qs.order_by('-timestamp')[:clamp(limit, 100)]]

    @strawberry.field
    def alerts(
        self, info: strawberry.Info, limit: Optional[int] = None,
        severity: Optional[Severity] = None, status: Optional[AlertStatus] = None,
    ) -> list[AlertType]:
        info.context.require_scope('read:alerts')
        qs = Alert.objects.filter(stream_id=self.id)
        if severity:
            qs = qs.filter(severity=severity.value)
        if status:
            qs = qs.filter(status=status.value)
        return [AlertType.from_model(a) for a in qs[:clamp(limit)]]

    @strawberry.field
    def annotations(self, info: strawberry.Info, limit: Optional[int] = None) -> list[AnnotationType]:
        info.context.require_scope('read:streams')
        qs = StreamAnnotation.objects.filter(stream_id=self.id)
        return [AnnotationType.from_model(a) for a in qs[:clamp(limit)]]

    @strawberry.field
    def rollups(
        self, info: strawberry.Info, period: RollupPeriod = RollupPeriod.HOURLY, limit: Optional[int] = None,
    ) -> list[RollupType]:
        info.context.require_scope('read:streams')
        qs = StreamRollup.objects.filter(stream_id=self.id, period=period.value)
        return [RollupType.from_model(r) for r in qs[:clamp(limit, 24)]]


@strawberry.type
class WorkspaceType:
    id: int
    name: str
    slug: str

    @classmethod
    def from_model(cls, w: Workspace):
        return cls(id=w.id, name=w.name, slug=w.slug)

    @strawberry.field
    def streams(self, info: strawberry.Info, limit: Optional[int] = None) -> list[StreamType]:
        info.context.require_scope('read:streams')
        return [StreamType.from_model(s) for s in Stream.objects.filter(workspace_id=self.id)[:clamp(limit)]]


@strawberry.type
class StreamEvent:
    """A live event pushed over a subscription."""

    type: str
    id: Optional[int] = None
    alert_id: Optional[int] = None
    value: Optional[float] = None
    score: Optional[float] = None
    severity: Optional[str] = None
    timestamp: Optional[str] = None
