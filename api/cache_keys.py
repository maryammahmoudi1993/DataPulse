from django.core.cache import cache


def stream_list_key(user_id: int | None) -> str:
    """Return the cache key of a user's stream list (``None`` is the anonymous demo visitor)."""
    return f'stream_list:user:{user_id if user_id is not None else "anon"}'


def alert_list_key(stream_id: int, severity: str | None, status: str | None) -> str:
    """Return the cache key of a stream's alert list for one severity/status filter."""
    severity = severity.upper() if severity else None
    status = status.upper() if status else None
    return f'alert_list:stream:{stream_id}:sev:{severity}:st:{status}'


def stream_stats_key(stream_id: int) -> str:
    return f'stream_stats:{stream_id}'


def invalidate_stream_cache(user_id: int | None) -> None:
    """Call after any stream write for this user."""
    cache.delete(stream_list_key(user_id))


def invalidate_workspace_stream_cache(workspace) -> None:
    """Drop the cached stream list of everyone who can see ``workspace``.

    A stream belongs to a workspace, not to one user, so a write by one
    member must not leave the other members (or the anonymous demo
    visitor) looking at a stale list.
    """
    user_ids = {workspace.owner_id, None}
    user_ids.update(workspace.memberships.values_list('user_id', flat=True))
    user_ids.update(workspace.members.values_list('pk', flat=True))
    cache.delete_many([stream_list_key(user_id) for user_id in user_ids])


def invalidate_alert_cache(stream_id: int) -> None:
    """Call after any alert write for this stream."""
    from alerts.models import Alert
    severities = [None] + [value for value, _ in Alert.SEVERITY_CHOICES]
    statuses = [None] + [value for value, _ in Alert.STATUS_CHOICES]
    cache.delete_many([
        alert_list_key(stream_id, severity, status)
        for severity in severities
        for status in statuses
    ])
