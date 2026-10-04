import logging

import requests
from celery import shared_task

logger = logging.getLogger(__name__)


def _notify(task, alert_id, integration_model, channel, send, ok_code):
    """Send one alert over one channel, recording the outcome in ``NotificationLog``."""
    from alerts.models import Alert
    from .models import NotificationLog

    try:
        alert = Alert.objects.select_related('stream__workspace').get(id=alert_id)
        integration = integration_model.objects.get(workspace=alert.stream.workspace, is_active=True)
    except (Alert.DoesNotExist, integration_model.DoesNotExist):
        return

    if not integration.should_notify(alert.severity):
        NotificationLog.objects.create(alert=alert, channel=channel, status=NotificationLog.STATUS_SKIPPED)
        return

    try:
        send(alert, integration)
    except requests.RequestException as exc:
        NotificationLog.objects.create(
            alert=alert, channel=channel, status=NotificationLog.STATUS_ERROR,
            response_code=getattr(exc.response, 'status_code', None), error=str(exc),
        )
        raise task.retry(exc=exc)

    NotificationLog.objects.create(
        alert=alert, channel=channel, status=NotificationLog.STATUS_OK, response_code=ok_code,
    )
    logger.info('%s notification sent', channel, extra={
        'alert_id': alert_id, 'workspace_id': alert.stream.workspace_id,
    })


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def dispatch_slack_notification(self, alert_id: int) -> None:
    from .models import NotificationLog, SlackIntegration
    from .slack import send_slack_alert

    _notify(self, alert_id, SlackIntegration, NotificationLog.CHANNEL_SLACK, send_slack_alert, 200)


@shared_task(bind=True, max_retries=2, default_retry_delay=15)
def dispatch_pagerduty_incident(self, alert_id: int) -> None:
    from .models import NotificationLog, PagerDutyIntegration
    from .pagerduty import send_pagerduty_incident

    _notify(self, alert_id, PagerDutyIntegration, NotificationLog.CHANNEL_PAGERDUTY,
            send_pagerduty_incident, 202)
