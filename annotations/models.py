from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class StreamAnnotation(models.Model):
    """A user-placed note on a stream's time axis (deploy, incident, config change)."""

    TYPE_EVENT = 'EVENT'  # single timestamp
    TYPE_MARKER = 'MARKER'  # same as EVENT, different visual
    TYPE_REGION = 'REGION'  # start + end timestamp
    TYPE_CHOICES = [
        (TYPE_EVENT, 'Event'),
        (TYPE_MARKER, 'Marker'),
        (TYPE_REGION, 'Region'),
    ]

    COLOR_CHOICES = [
        ('gray', 'Gray'),
        ('blue', 'Blue'),
        ('green', 'Green'),
        ('yellow', 'Yellow'),
        ('orange', 'Orange'),
        ('red', 'Red'),
    ]

    stream = models.ForeignKey('streams.Stream', on_delete=models.CASCADE, related_name='annotations')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='annotations',
    )
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    annotation_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_EVENT)
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default='blue')
    timestamp = models.DateTimeField(db_index=True)
    end_timestamp = models.DateTimeField(null=True, blank=True, help_text='Required for REGION type.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['timestamp']
        indexes = [models.Index(fields=['stream', 'timestamp'])]

    def __str__(self):
        return f'Annotation[{self.annotation_type}] {self.label} on {self.stream_id}'

    def clean(self):
        if self.annotation_type == self.TYPE_REGION and not self.end_timestamp:
            raise ValidationError('REGION annotations require end_timestamp.')
        if self.end_timestamp and self.end_timestamp <= self.timestamp:
            raise ValidationError('end_timestamp must be after timestamp.')
