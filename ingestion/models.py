from django.db import models


class DataPoint(models.Model):
    stream = models.ForeignKey('streams.Stream', on_delete=models.CASCADE, related_name='data_points')
    timestamp = models.DateTimeField(db_index=True)
    value = models.FloatField()
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['stream', 'timestamp'])]

    def __str__(self):
        return f'{self.stream_id}@{self.timestamp}'
