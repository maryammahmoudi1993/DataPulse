import logging

from django.db import transaction

logger = logging.getLogger(__name__)


def log_event(*, workspace, action, actor=None, target_user=None, stream=None, metadata=None, ip_address=None):
    """Record an audit event without ever raising.

    The write runs in its own savepoint so a failure cannot poison the caller's
    transaction; any exception is logged and swallowed.

    Args:
        workspace: Workspace the event belongs to.
        action: One of the ``AuditEvent.ACTION_CHOICES`` keys.
        actor: User who performed the action, if any.
        target_user: User the action was applied to, if any.
        stream: Stream the action concerns, if any.
        metadata: Extra JSON-serialisable details.
        ip_address: Client IP address of the request.
    """
    from .models import AuditEvent
    try:
        with transaction.atomic():
            AuditEvent.objects.create(
                workspace=workspace,
                actor=actor,
                action=action,
                target_user=target_user,
                stream=stream,
                metadata=metadata or {},
                ip_address=ip_address,
            )
    except Exception as exc:  # noqa: BLE001 - audit logging must never break the request
        logger.error('AuditEvent write failed', extra={'action': action, 'exc': str(exc)})


def get_client_ip(request):
    """Return the client IP of a request.

    Args:
        request: Django request.

    Returns:
        First ``X-Forwarded-For`` address when present, else ``REMOTE_ADDR``.
    """
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')
