from rest_framework import serializers

from alerts.models import Alert, AlertRule, WebhookEndpoint
from audit.models import AuditEvent
from ingestion.models import DataPoint
from integrations.models import NotificationLog, PagerDutyIntegration, SlackIntegration
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
