import logging

from django.utils import timezone

from alerts.models import AlertRule
from alerts.services import create_alert
from detection.base import DetectionResult

logger = logging.getLogger(__name__)

RULE_DETECTOR_TYPE = 'RULE'


def evaluate_rules(stream, point, previous_value):
    """Evaluate the stream's active alert rules against a new data point.

    Never raises: a broken rule is logged and skipped, so rule evaluation can
    not interfere with ingestion or ML detection.

    Args:
        stream: The Stream the point belongs to.
        point: The persisted DataPoint that just arrived.
        previous_value: The value before ``point``, or None for the first point.
    """
    try:
        rules = list(AlertRule.objects.filter(stream=stream, is_active=True))
    except Exception:
        logger.exception('Alert rule lookup failed', extra={'stream_id': stream.id})
        return

    for rule in rules:
        try:
            _evaluate_rule(rule, stream, point, previous_value)
        except Exception:
            logger.exception('Alert rule evaluation failed', extra={'rule_id': rule.id, 'stream_id': stream.id})


def _breach(rule, value, previous_value):
    """Return the breach magnitude when ``rule`` is triggered, else None."""
    if rule.condition == AlertRule.CONDITION_ABOVE and value > rule.threshold:
        return value - rule.threshold
    if rule.condition == AlertRule.CONDITION_BELOW and value < rule.threshold:
        return rule.threshold - value
    if rule.condition == AlertRule.CONDITION_CHANGE and previous_value is not None and abs(previous_value) > 1e-9:
        change_pct = abs((value - previous_value) / previous_value) * 100
        if change_pct > rule.threshold:
            return change_pct - rule.threshold
    return None


def _evaluate_rule(rule, stream, point, previous_value):
    now = timezone.now()
    if rule.last_fired is not None:
        elapsed_minutes = (now - rule.last_fired).total_seconds() / 60
        if elapsed_minutes < rule.cooldown_minutes:
            return

    magnitude = _breach(rule, point.value, previous_value)
    if magnitude is None:
        return

    result = DetectionResult(is_anomaly=True, score=magnitude, severity=rule.severity, value=point.value)
    alert = create_alert(stream, point, result, detector_type=RULE_DETECTOR_TYPE)
    if alert is None:
        return

    rule.last_fired = now
    rule.save(update_fields=['last_fired'])
    logger.info('Alert rule fired', extra={
        'rule_id': rule.id,
        'rule_name': rule.name,
        'stream_id': stream.id,
        'alert_id': alert.id,
    })
