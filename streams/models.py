from django.conf import settings
from django.db import models


class Workspace(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='member_workspaces',
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def accessible_to(cls, user):
        """Return workspaces a user may see.

        Args:
            user: Django user, possibly anonymous.

        Returns:
            QuerySet of workspaces the user owns or is a member of. Anonymous
            users only see the public demo workspace, and only when
            ``DEMO_PUBLIC_ACCESS`` is enabled.
        """
        if user is not None and user.is_authenticated:
            return cls.objects.filter(
                models.Q(owner=user) | models.Q(members=user) | models.Q(memberships__user=user)
            ).distinct()
        if getattr(settings, 'DEMO_PUBLIC_ACCESS', False):
            return cls.objects.filter(slug=settings.DEMO_WORKSPACE_SLUG)
        return cls.objects.none()


class Stream(models.Model):
    SOURCE_SIMULATOR = 'SIMULATOR'
    SOURCE_CSV = 'CSV'
    SOURCE_HTTP = 'HTTP'
    SOURCE_CHOICES = [
        (SOURCE_SIMULATOR, 'IoT Simulator'),
        (SOURCE_CSV, 'CSV Upload'),
        (SOURCE_HTTP, 'HTTP Endpoint'),
    ]

    DETECTOR_ZSCORE = 'ZSCORE'
    DETECTOR_IQR = 'IQR'
    DETECTOR_LSTM = 'LSTM'
    DETECTOR_ENSEMBLE = 'ENSEMBLE'
    DETECTOR_CHOICES = [
        (DETECTOR_ZSCORE, 'Z-Score'),
        (DETECTOR_IQR, 'IQR'),
        (DETECTOR_LSTM, 'LSTM'),
        (DETECTOR_ENSEMBLE, 'Ensemble'),
    ]

    STATUS_ACTIVE = 'ACTIVE'
    STATUS_PAUSED = 'PAUSED'
    STATUS_ERROR = 'ERROR'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_ERROR, 'Error'),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='streams')
    name = models.CharField(max_length=120)
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_config = models.JSONField(default=dict)
    sampling_interval = models.PositiveIntegerField(default=5, help_text='seconds')
    detector_type = models.CharField(max_length=20, choices=DETECTOR_CHOICES, default=DETECTOR_ZSCORE)
    detector_config = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    retention_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Auto-delete DataPoints older than N days. Null = keep forever.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.workspace.slug}/{self.name}'


class StreamRollup(models.Model):
    """Pre-computed aggregates per stream and time bucket.

    Written by the rollup Celery tasks and read by the analytics API. The API
    exposes rollups read-only.
    """

    PERIOD_HOURLY = 'HOURLY'
    PERIOD_DAILY = 'DAILY'
    PERIOD_CHOICES = [
        (PERIOD_HOURLY, 'Hourly'),
        (PERIOD_DAILY, 'Daily'),
    ]

    stream = models.ForeignKey(Stream, on_delete=models.CASCADE, related_name='rollups')
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    bucket_ts = models.DateTimeField(db_index=True, help_text='Start of the bucket, truncated to the period.')
    count = models.PositiveIntegerField()
    mean = models.FloatField()
    std = models.FloatField()
    min_val = models.FloatField()
    max_val = models.FloatField()
    p50 = models.FloatField()
    p95 = models.FloatField()
    p99 = models.FloatField()
    alert_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('stream', 'period', 'bucket_ts')
        ordering = ['-bucket_ts']
        indexes = [models.Index(fields=['stream', 'period', 'bucket_ts'])]

    def __str__(self):
        return f'Rollup[{self.period}] stream={self.stream_id} {self.bucket_ts}'
