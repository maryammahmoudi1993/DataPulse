from django.conf import settings
from django.db import models


class Alert(models.Model):
    SEVERITY_LOW = 'LOW'
    SEVERITY_MEDIUM = 'MEDIUM'
    SEVERITY_HIGH = 'HIGH'
    SEVERITY_CRITICAL = 'CRITICAL'
    SEVERITY_CHOICES = [
        (SEVERITY_LOW, 'Low'),
        (SEVERITY_MEDIUM, 'Medium'),
        (SEVERITY_HIGH, 'High'),
        (SEVERITY_CRITICAL, 'Critical'),
    ]
    SEVERITY_RANK = {
        SEVERITY_LOW: 0,
        SEVERITY_MEDIUM: 1,
        SEVERITY_HIGH: 2,
        SEVERITY_CRITICAL: 3,
    }

    STATUS_OPEN = 'OPEN'
    STATUS_ACKNOWLEDGED = 'ACKNOWLEDGED'
    STATUS_RESOLVED = 'RESOLVED'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_ACKNOWLEDGED, 'Acknowledged'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    stream = models.ForeignKey('streams.Stream', on_delete=models.CASCADE, related_name='alerts')
    data_point = models.ForeignKey(
        'ingestion.DataPoint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alerts',
    )
    timestamp = models.DateTimeField(db_index=True)
    value = models.FloatField()
    anomaly_score = models.FloatField()
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    detector_type = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_alerts',
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp', '-id']
        indexes = [models.Index(fields=['stream', 'severity', 'created_at'])]

    def __str__(self):
        return f'{self.severity} alert on stream {self.stream_id} ({self.status})'


class WebhookEndpoint(models.Model):
    workspace = models.ForeignKey('streams.Workspace', on_delete=models.CASCADE, related_name='webhooks')
    name = models.CharField(max_length=120)
    url = models.URLField()
    min_severity = models.CharField(
        max_length=10,
        choices=Alert.SEVERITY_CHOICES,
        default=Alert.SEVERITY_HIGH,
    )
    secret = models.CharField(max_length=128, blank=True, help_text='Used to sign payloads (HMAC-SHA256).')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} -> {self.url}'

    def accepts(self, severity):
        """Return True when an alert of this severity should be delivered here."""
        return self.is_active and Alert.SEVERITY_RANK[severity] >= Alert.SEVERITY_RANK[self.min_severity]


class AlertRule(models.Model):
    """A user-defined threshold rule that fires independently of ML detection."""

    CONDITION_ABOVE = 'ABOVE'
    CONDITION_BELOW = 'BELOW'
    CONDITION_CHANGE = 'CHANGE_PCT'
    CONDITION_CHOICES = [
        (CONDITION_ABOVE, 'Value above threshold'),
        (CONDITION_BELOW, 'Value below threshold'),
        (CONDITION_CHANGE, 'Change exceeds % threshold'),
    ]

    stream = models.ForeignKey('streams.Stream', on_delete=models.CASCADE, related_name='alert_rules')
    name = models.CharField(max_length=120)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    threshold = models.FloatField()
    severity = models.CharField(max_length=10, choices=Alert.SEVERITY_CHOICES, default=Alert.SEVERITY_HIGH)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alert_rules',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_fired = models.DateTimeField(null=True, blank=True)
    cooldown_minutes = models.PositiveIntegerField(
        default=5,
        help_text='Minimum minutes between firings of this rule.',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['stream', 'is_active'])]

    def __str__(self):
        return f'Rule[{self.condition}] {self.name} on stream {self.stream_id}'
