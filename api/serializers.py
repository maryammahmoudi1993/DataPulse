from django.conf import settings
from rest_framework import serializers

from alerts.models import Alert, AlertRule, WebhookEndpoint
from annotations.models import StreamAnnotation
from api_keys.models import APIKey
from audit.models import AuditEvent
from ingestion.models import DataPoint
from integrations.models import NotificationLog, PagerDutyIntegration, SlackIntegration
from sharing.models import DashboardShare
from streams.models import Stream, StreamRollup, Workspace


class WorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ['id', 'name', 'slug', 'owner', 'created_at']
        read_only_fields = ['id', 'owner', 'created_at']


class StreamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stream
        fields = [
            'id',
            'workspace',
            'name',
            'source_type',
            'source_config',
            'sampling_interval',
            'detector_type',
            'detector_config',
            'status',
            'retention_days',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class DataPointSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataPoint
        fields = ['id', 'stream', 'timestamp', 'value', 'metadata']
        read_only_fields = ['id', 'stream']


class AlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alert
        fields = [
            'id',
            'stream',
            'timestamp',
            'value',
            'anomaly_score',
            'severity',
            'detector_type',
            'status',
            'acknowledged_at',
            'created_at',
        ]
        read_only_fields = fields


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = ['id', 'workspace', 'name', 'url', 'min_severity', 'secret', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {'secret': {'write_only': True}}


class AuditEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source='actor.username', read_only=True, default=None)
    target_username = serializers.CharField(source='target_user.username', read_only=True, default=None)
    stream_name = serializers.CharField(source='stream.name', read_only=True, default=None)

    class Meta:
        model = AuditEvent
        fields = [
            'id', 'action', 'actor_username', 'target_username',
            'stream_name', 'metadata', 'ip_address', 'created_at',
        ]


class _IntegrationSerializer(serializers.ModelSerializer):
    """Shared validation for notification-channel integrations."""

    def validate_min_severity(self, value):
        if value not in dict(Alert.SEVERITY_CHOICES):
            raise serializers.ValidationError(f'Must be one of {list(dict(Alert.SEVERITY_CHOICES))}.')
        return value


class SlackIntegrationSerializer(_IntegrationSerializer):
    class Meta:
        model = SlackIntegration
        fields = ['id', 'workspace', 'webhook_url', 'min_severity', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {'webhook_url': {'write_only': True}}


class PagerDutyIntegrationSerializer(_IntegrationSerializer):
    class Meta:
        model = PagerDutyIntegration
        fields = ['id', 'workspace', 'routing_key', 'min_severity', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {'routing_key': {'write_only': True}}


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = ['id', 'alert', 'channel', 'status', 'response_code', 'error', 'created_at']
        read_only_fields = fields


class StreamRollupSerializer(serializers.ModelSerializer):
    class Meta:
        model = StreamRollup
        fields = ['period', 'bucket_ts', 'count', 'mean', 'std', 'min_val', 'max_val',
                  'p50', 'p95', 'p99', 'alert_count']
        read_only_fields = fields


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = ['id', 'stream', 'name', 'condition', 'threshold', 'severity',
                  'is_active', 'cooldown_minutes', 'last_fired', 'created_at']
        read_only_fields = ['id', 'stream', 'last_fired', 'created_at']


class APIKeySerializer(serializers.ModelSerializer):
    """API key metadata. ``raw_key`` is only present in the creation response."""

    raw_key = serializers.SerializerMethodField()
    workspace = serializers.PrimaryKeyRelatedField(queryset=Workspace.objects.all())
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=APIKey.SCOPE_CHOICES),
        allow_empty=False,
        default=lambda: [APIKey.SCOPE_READ_STREAMS],
    )

    class Meta:
        model = APIKey
        fields = ['id', 'workspace', 'name', 'prefix', 'scopes', 'is_active',
                  'last_used', 'expires_at', 'created_at', 'raw_key']
        read_only_fields = ['id', 'prefix', 'last_used', 'created_at', 'raw_key']

    def get_raw_key(self, obj) -> str | None:
        # Attached to the instance by the create view and never persisted.
        return getattr(obj, '_raw_key', None)

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop('workspace', None)  # a key never moves between workspaces
        return attrs


class StreamAnnotationSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, default=None)

    class Meta:
        model = StreamAnnotation
        fields = ['id', 'stream', 'label', 'description', 'annotation_type', 'color',
                  'timestamp', 'end_timestamp', 'created_by_username', 'created_at', 'updated_at']
        read_only_fields = ['id', 'stream', 'created_by_username', 'created_at', 'updated_at']

    def validate(self, attrs):
        def current(name, default=None):
            if name in attrs:
                return attrs[name]
            return getattr(self.instance, name, default)

        start = current('timestamp')
        end = current('end_timestamp')
        if current('annotation_type', StreamAnnotation.TYPE_EVENT) == StreamAnnotation.TYPE_REGION and not end:
            raise serializers.ValidationError({'end_timestamp': 'REGION annotations require end_timestamp.'})
        if end and start and end <= start:
            raise serializers.ValidationError({'end_timestamp': 'end_timestamp must be after timestamp.'})
        return attrs


class DashboardShareSerializer(serializers.ModelSerializer):
    share_url = serializers.SerializerMethodField()

    class Meta:
        model = DashboardShare
        fields = ['id', 'stream', 'title', 'token', 'expires_at', 'is_active',
                  'view_count', 'max_points', 'created_at', 'share_url']
        read_only_fields = ['id', 'stream', 'token', 'view_count', 'created_at', 'share_url']

    def get_share_url(self, obj) -> str:
        return f'{settings.INVITE_BASE_URL}/share/{obj.token}'
