import requests

PAGERDUTY_EVENTS_URL = 'https://events.pagerduty.com/v2/enqueue'

PD_SEVERITY_MAP = {
    'LOW': 'info',
    'MEDIUM': 'warning',
    'HIGH': 'error',
    'CRITICAL': 'critical',
}


def send_pagerduty_incident(alert, integration) -> str:
    """Trigger a PagerDuty incident through the Events API v2.

    The ``dedup_key`` is derived from the alert id, so repeated calls for the
    same alert update one incident instead of opening several.

    Returns:
        The status reported by PagerDuty (``'success'``), or ``'OK'``.

    Raises:
        requests.RequestException: If the Events API call fails.
    """
    payload = {
        'routing_key': integration.routing_key,
        'event_action': 'trigger',
        'dedup_key': f'datapulse-alert-{alert.id}',
        'payload': {
            'summary': (
                f'{alert.severity} anomaly on {alert.stream.name} — '
                f'score {alert.anomaly_score:.2f}'
            ),
            'severity': PD_SEVERITY_MAP.get(alert.severity, 'error'),
            'source': 'DataPulse',
            'timestamp': alert.timestamp.isoformat(),
            'custom_details': {
                'stream_id': alert.stream_id,
                'stream_name': alert.stream.name,
                'workspace': alert.stream.workspace.slug,
                'value': alert.value,
                'anomaly_score': alert.anomaly_score,
                'detector_type': alert.detector_type,
                'alert_id': alert.id,
            },
        },
    }
    response = requests.post(PAGERDUTY_EVENTS_URL, json=payload, timeout=5)
    response.raise_for_status()
    return response.json().get('status', 'OK')
