from datetime import timedelta

import pytest
from django.utils import timezone

from alerts.models import Alert, AlertRule
from alerts.rules import evaluate_rules
from ingestion.models import DataPoint
from streams.models import Stream, Workspace


@pytest.fixture(autouse=True)
def no_dedup(settings):
    # Alert deduplication would otherwise mask what the rule cooldown does.
    settings.ALERT_DEDUP_WINDOW_MINUTES = 0


@pytest.fixture
def stream(db):
    workspace = Workspace.objects.create(name='W', slug='w')
    return Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)


def _rule(stream, condition, threshold, **kwargs):
    return AlertRule.objects.create(stream=stream, name='r', condition=condition, threshold=threshold, **kwargs)


def _evaluate(stream, value, previous=None):
    point = DataPoint.objects.create(stream=stream, timestamp=timezone.now(), value=value)
    evaluate_rules(stream, point, previous)


def test_rule_fires_above_threshold(stream):
    _rule(stream, AlertRule.CONDITION_ABOVE, 10.0, severity=Alert.SEVERITY_CRITICAL)

    _evaluate(stream, 15.0)

    alert = Alert.objects.get(stream=stream)
    assert alert.severity == Alert.SEVERITY_CRITICAL
    assert alert.value == 15.0
    assert alert.detector_type == 'RULE'
    assert AlertRule.objects.get().last_fired is not None


def test_rule_does_not_fire_below_threshold(stream):
    _rule(stream, AlertRule.CONDITION_ABOVE, 10.0)

    _evaluate(stream, 5.0)

    assert not Alert.objects.exists()


def test_rule_fires_below_threshold(stream):
    _rule(stream, AlertRule.CONDITION_BELOW, 10.0)

    _evaluate(stream, 5.0)

    assert Alert.objects.filter(stream=stream).count() == 1


def test_change_pct_rule_fires_on_large_jump(stream):
    _rule(stream, AlertRule.CONDITION_CHANGE, 30.0)

    _evaluate(stream, 150.0, previous=100.0)

    assert Alert.objects.filter(stream=stream).count() == 1


def test_change_pct_rule_ignores_small_change(stream):
    _rule(stream, AlertRule.CONDITION_CHANGE, 30.0)

    _evaluate(stream, 105.0, previous=100.0)

    assert not Alert.objects.exists()


def test_change_pct_rule_never_fires_without_previous_value(stream):
    _rule(stream, AlertRule.CONDITION_CHANGE, 30.0)

    _evaluate(stream, 500.0, previous=None)

    assert not Alert.objects.exists()


def test_cooldown_prevents_repeated_firing(stream):
    rule = _rule(stream, AlertRule.CONDITION_ABOVE, 10.0, cooldown_minutes=5)

    _evaluate(stream, 15.0)
    _evaluate(stream, 16.0)
    assert Alert.objects.count() == 1

    AlertRule.objects.filter(pk=rule.pk).update(last_fired=timezone.now() - timedelta(minutes=6))
    _evaluate(stream, 17.0)
    assert Alert.objects.count() == 2


def test_inactive_rule_never_fires(stream):
    _rule(stream, AlertRule.CONDITION_ABOVE, 10.0, is_active=False)

    _evaluate(stream, 1000.0)

    assert not Alert.objects.exists()


def test_rule_error_is_swallowed(stream, monkeypatch):
    _rule(stream, AlertRule.CONDITION_ABOVE, 10.0)

    def boom(*args, **kwargs):
        raise RuntimeError('boom')

    monkeypatch.setattr('alerts.rules.create_alert', boom)

    _evaluate(stream, 15.0)

    assert not Alert.objects.exists()
