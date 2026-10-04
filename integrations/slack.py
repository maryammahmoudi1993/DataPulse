import json

import requests

SEVERITY_EMOJI = {
    'LOW': 'ℹ️',
    'MEDIUM': '⚠️',
    'HIGH': '🔴',
    'CRITICAL': '🚨',
}


def build_slack_payload(alert) -> dict:
    """Build the Block Kit message for ``alert``."""
    emoji = SEVERITY_EMOJI.get(alert.severity, '⚠️')
    return {
        'text': f'{emoji} {alert.severity} anomaly on {alert.stream.name}',
        'blocks': [
            {
                'type': 'header',
                'text': {
                    'type': 'plain_text',
                    'text': f'{emoji} Anomaly detected — {alert.severity}',
                    'emoji': True,
                },
            },
            {
                'type': 'section',
                'fields': [
                    {'type': 'mrkdwn', 'text': f'*Stream:*\n{alert.stream.name}'},
                    {'type': 'mrkdwn', 'text': f'*Workspace:*\n{alert.stream.workspace.slug}'},
                    {'type': 'mrkdwn', 'text': f'*Score:*\n{alert.anomaly_score:.3f}'},
                    {'type': 'mrkdwn', 'text': f'*Detector:*\n{alert.detector_type}'},
                    {'type': 'mrkdwn', 'text': f'*Value:*\n{alert.value}'},
                    {'type': 'mrkdwn', 'text': f'*Time:*\n{alert.timestamp.strftime("%Y-%m-%d %H:%M UTC")}'},
                ],
            },
            {
                'type': 'context',
                'elements': [{'type': 'mrkdwn', 'text': f'DataPulse · alert #{alert.id}'}],
            },
        ],
    }


def send_slack_alert(alert, integration) -> str:
    """Post a Slack Block Kit message.

    Returns:
        ``'OK'`` on success.

    Raises:
        requests.RequestException: If the webhook call fails.
    """
    response = requests.post(
        integration.webhook_url,
        data=json.dumps(build_slack_payload(alert)),
        headers={'Content-Type': 'application/json'},
        timeout=5,
    )
    response.raise_for_status()
    return 'OK'
