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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


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
    DETECTOR_CHOICES = [
        (DETECTOR_ZSCORE, 'Z-Score'),
        (DETECTOR_IQR, 'IQR'),
        (DETECTOR_LSTM, 'LSTM'),
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.workspace.slug}/{self.name}'
