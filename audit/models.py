from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """A record of a notable action taken inside a workspace."""

    ACTION_CHOICES = [
        ('STREAM_CREATED', 'Stream created'),
        ('STREAM_PAUSED', 'Stream paused'),
        ('STREAM_RESUMED', 'Stream resumed'),
        ('STREAM_DELETED', 'Stream deleted'),
        ('MEMBER_INVITED', 'Member invited'),
        ('MEMBER_ROLE_CHANGED', 'Member role changed'),
        ('MEMBER_REMOVED', 'Member removed'),
        ('ALERT_ACKNOWLEDGED', 'Alert acknowledged'),
        ('ALERT_RESOLVED', 'Alert resolved'),
        ('EXPORT_REQUESTED', 'Export requested'),
        ('LSTM_TRAINING_TRIGGERED', 'LSTM training triggered'),
        ('WEBHOOK_CREATED', 'Webhook created'),
        ('WEBHOOK_DELETED', 'Webhook deleted'),
        ('ALERT_RULE_CREATED', 'Alert rule created'),
        ('ALERT_RULE_DELETED', 'Alert rule deleted'),
    ]

    workspace = models.ForeignKey('streams.Workspace', on_delete=models.CASCADE, related_name='audit_events')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_events',
    )
    action = models.CharField(max_length=40, choices=ACTION_CHOICES, db_index=True)
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_events_as_target',
    )
    stream = models.ForeignKey(
        'streams.Stream', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_events',
    )
    metadata = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['workspace', 'created_at']),
            models.Index(fields=['workspace', 'action']),
        ]

    def __str__(self):
        actor = self.actor.username if self.actor else 'system'
        return f'AuditEvent[{self.action}] by {actor} in {self.workspace.slug}'
