import logging
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

DIGEST_WINDOW_HOURS = 24
DIGEST_RECENT_LIMIT = 10


@shared_task
def send_daily_alert_digest():
    """Email each workspace owner a summary of the last 24 hours of alerts.

    Workspaces without alerts in the window, or without an owner who has an
    email address, are skipped. A failure to deliver one digest does not stop
    the others.

    Returns:
        Dict with the number of ``digests_sent``.
    """
    from accounts.models import UserWorkspace
    from alerts.models import Alert
    from streams.models import Workspace

    sent = 0
    now = timezone.now()
    cutoff = now - timedelta(hours=DIGEST_WINDOW_HOURS)

    for workspace in Workspace.objects.all():
        alerts = Alert.objects.filter(stream__workspace=workspace, created_at__gte=cutoff)
        if not alerts.exists():
            continue

        owners = UserWorkspace.objects.filter(
            workspace=workspace,
            role=UserWorkspace.ROLE_OWNER,
        ).select_related('user')
        emails = [m.user.email for m in owners if m.user.email]
        if not emails:
            continue

        try:
            delivered = _send_email(
                to=emails,
                subject=f'[DataPulse] Daily alert digest - {workspace.name}',
                body=_build_digest_body(workspace, alerts, now),
            )
        except (smtplib.SMTPException, OSError, ValueError) as e:
            logger.warning('Alert digest failed', extra={'workspace_id': workspace.id, 'error': str(e)})
            continue
        if not delivered:
            continue
        sent += 1
        logger.info('Alert digest sent', extra={'workspace_id': workspace.id, 'alert_count': alerts.count()})

    return {'digests_sent': sent}


def _build_digest_body(workspace, alerts, now):
    """Render the plain-text digest for a workspace.

    Args:
        workspace: The Workspace being summarised.
        alerts: QuerySet of the alerts in the digest window.
        now: End of the digest window.

    Returns:
        The email body as a string.
    """
    from alerts.models import Alert

    counts = {severity: 0 for severity, _ in Alert.SEVERITY_CHOICES}
    for alert in alerts:
        counts[alert.severity] += 1

    lines = [
        f'Alert digest for workspace: {workspace.name}',
        f'Period: last {DIGEST_WINDOW_HOURS} hours ending {now.strftime("%Y-%m-%d %H:%M UTC")}',
        '',
        f'Total alerts: {sum(counts.values())}',
        '',
    ]
    for severity, label in Alert.SEVERITY_CHOICES:
        if counts[severity]:
            lines.append(f'  {label:10s} {counts[severity]}')
    lines += ['', f'{DIGEST_RECENT_LIMIT} most recent:']
    recent = alerts.select_related('stream').order_by('-created_at')[:DIGEST_RECENT_LIMIT]
    for alert in recent:
        lines.append(
            f'  [{alert.severity}] stream={alert.stream.name} '
            f'score={alert.anomaly_score:.2f} at {alert.timestamp.strftime("%H:%M:%S")}'
        )
    return '\n'.join(lines)


def _send_email(to, subject, body):
    """Send a plain-text email through the configured SMTP server.

    Does nothing, apart from logging a warning, when ``SMTP_USER`` is not set.

    Args:
        to: List of recipient addresses.
        subject: Subject line.
        body: Plain-text body.

    Returns:
        True when the message was handed to the SMTP server, False when SMTP
        is not configured.
    """
    if not settings.SMTP_USER:
        logger.warning('SMTP_USER not configured - digest not sent')
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = settings.SMTP_FROM
    msg['To'] = ', '.join(to)
    msg.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
    return True
