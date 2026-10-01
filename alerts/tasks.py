import hashlib
import hmac
import json
import logging

import requests
from celery import shared_task
from django.conf import settings

from alerts.models import Alert, WebhookEndpoint
from datapulse.metrics import webhooks_dispatched

logger = logging.getLogger(__name__)


def build_payload(alert):
    """Serialise an alert into the JSON body sent to webhooks."""
    return {
        'alert_id': alert.id,
        'stream_id': alert.stream_id,
        'stream': alert.stream.name,
        'severity': alert.severity,
        'score': alert.anomaly_score,
        'value': alert.value,
        'detector': alert.detector_type,
        'timestamp': alert.timestamp.isoformat(),
    }


@shared_task
def dispatch_webhooks(alert_id):
    """Deliver an alert to every matching webhook endpoint in its workspace.

    Args:
        alert_id: Primary key of the alert.

    Returns:
        Number of endpoints that acknowledged the delivery.
    """
    try:
        alert = Alert.objects.select_related('stream__workspace').get(pk=alert_id)
    except Alert.DoesNotExist:
        return 0

    body = json.dumps(build_payload(alert)).encode()
    delivered = 0
    endpoints = WebhookEndpoint.objects.filter(workspace=alert.stream.workspace, is_active=True)
    for endpoint in endpoints:
        if not endpoint.accepts(alert.severity):
            continue
        headers = {'Content-Type': 'application/json'}
        if endpoint.secret:
            digest = hmac.new(endpoint.secret.encode(), body, hashlib.sha256).hexdigest()
            headers['X-DataPulse-Signature'] = f'sha256={digest}'
        try:
            response = requests.post(
                endpoint.url,
                data=body,
                headers=headers,
                timeout=settings.ALERT_WEBHOOK_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            webhooks_dispatched.labels(status='ok').inc()
            delivered += 1
        except requests.RequestException as e:
            webhooks_dispatched.labels(status='error').inc()
            logger.warning('Webhook %s failed: %s', endpoint.pk, e)
    return delivered
