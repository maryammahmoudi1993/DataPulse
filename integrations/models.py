from django.db import models

from streams.models import Workspace

SEVERITY_RANK = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4}


class NotifyingIntegration(models.Model):
    """Shared fields and severity gate for per-workspace notification channels."""

    min_severity = models.CharField(max_length=20, default='HIGH',
                                    help_text='Only notify at or above this severity.')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def should_notify(self, severity: str) -> bool:
        """Return True when the integration is active and ``severity`` meets the minimum."""
        if not self.is_active:
            return False
        return SEVERITY_RANK.get(severity, 0) >= SEVERITY_RANK.get(self.min_severity, 0)


class SlackIntegration(NotifyingIntegration):
    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE,
                                     related_name='slack_integration')
    webhook_url = models.URLField()

    def __str__(self):
        return f'Slack[{self.workspace.slug}] active={self.is_active}'


class PagerDutyIntegration(NotifyingIntegration):
    workspace = models.OneToOneField(Workspace, on_delete=models.CASCADE,
                                     related_name='pagerduty_integration')
    routing_key = models.CharField(max_length=64)

    def __str__(self):
        return f'PagerDuty[{self.workspace.slug}] active={self.is_active}'


class NotificationLog(models.Model):
    """Append-only record of one outbound notification attempt."""

    CHANNEL_SLACK = 'SLACK'
    CHANNEL_PAGERDUTY = 'PAGERDUTY'
    CHANNEL_CHOICES = [
        (CHANNEL_SLACK, 'Slack'),
        (CHANNEL_PAGERDUTY, 'PagerDuty'),
    ]

    STATUS_OK = 'OK'
    STATUS_ERROR = 'ERROR'
    STATUS_SKIPPED = 'SKIPPED'
    STATUS_CHOICES = [
        (STATUS_OK, 'OK'),
        (STATUS_ERROR, 'Error'),
        (STATUS_SKIPPED, 'Skipped'),
    ]

    alert = models.ForeignKey('alerts.Alert', on_delete=models.CASCADE, related_name='notifications')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    response_code = models.IntegerField(null=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['alert', 'channel'])]

    def __str__(self):
        return f'Notification[{self.channel}] alert={self.alert_id} {self.status}'
