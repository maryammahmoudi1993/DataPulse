import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from streams.models import Stream


def _new_token() -> str:
    return str(uuid.uuid4())


class DashboardShare(models.Model):
    """A time-limited read-only share link for a single stream.

    The public endpoint that serves it does not require authentication.
    """

    stream = models.ForeignKey(Stream, on_delete=models.CASCADE, related_name='shares')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='dashboard_shares',
    )
    token = models.CharField(max_length=36, unique=True, default=_new_token)
    title = models.CharField(max_length=120, blank=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    view_count = models.PositiveIntegerField(default=0)
    max_points = models.PositiveIntegerField(default=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['token', 'is_active'])]

    def __str__(self):
        return f'Share[{self.token[:8]}…] stream={self.stream_id}'

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired
