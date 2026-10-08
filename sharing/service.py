from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import DashboardShare


def create_share(stream, created_by, title='', days=None, max_points=None):
    """Create a read-only share link for ``stream``.

    Args:
        stream: Stream to share.
        created_by: User creating the link.
        title: Optional display title; defaults to "<stream name> — live view".
        days: Lifetime in days; defaults to ``SHARE_LINK_TTL_DAYS``.
        max_points: Points exposed to viewers; defaults to ``SHARE_LINK_MAX_POINTS``.

    Returns:
        The saved DashboardShare.
    """
    return DashboardShare.objects.create(
        stream=stream,
        created_by=created_by,
        title=title or f'{stream.name} — live view',
        expires_at=timezone.now() + timedelta(days=days or settings.SHARE_LINK_TTL_DAYS),
        max_points=max_points or settings.SHARE_LINK_MAX_POINTS,
    )
