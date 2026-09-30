import json
import logging

from django.utils import timezone

EXTRA_FIELDS = (
    'stream_id', 'alert_id', 'task', 'duration_ms', 'score', 'is_anomaly', 'severity',
    'detector_a', 'detector_b', 'agreement_pct', 'exc',
)


class JSONFormatter(logging.Formatter):
    """Render log records as single-line JSON documents."""

    def format(self, record):
        """Serialise a record.

        Args:
            record: The log record to render.

        Returns:
            JSON string with timestamp, level, logger, message and any of
            the whitelisted structured fields attached via ``extra``.
        """
        payload = {
            'ts': timezone.now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        for key in EXTRA_FIELDS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload['exc'] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)
