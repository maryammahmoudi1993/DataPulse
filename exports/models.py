from django.conf import settings
from django.db import models


class ExportJob(models.Model):
    TYPE_DATAPOINTS = 'DATAPOINTS'
    TYPE_ALERTS = 'ALERTS'
    TYPE_CHOICES = [
        (TYPE_DATAPOINTS, 'Data Points'),
        (TYPE_ALERTS, 'Alerts'),
    ]

    STATUS_PENDING = 'PENDING'
    STATUS_PROCESSING = 'PROCESSING'
    STATUS_DONE = 'DONE'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    stream = models.ForeignKey('streams.Stream', on_delete=models.CASCADE, related_name='exports')
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='export_jobs',
    )
    export_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    file_path = models.CharField(max_length=500, blank=True)
    row_count = models.PositiveIntegerField(null=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Export[{self.export_type}] stream={self.stream_id} {self.status}'
