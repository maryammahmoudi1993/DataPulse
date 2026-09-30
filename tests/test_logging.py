import json
import logging

from datapulse.logging_config import JSONFormatter


def _record(**extra):
    record = logging.LogRecord('datapulse.test', logging.INFO, __file__, 1, 'hello %s', ('world',), None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formatter_emits_json_with_structured_fields():
    payload = json.loads(JSONFormatter().format(_record(stream_id=3, score=2.5, ignored='x')))

    assert payload['message'] == 'hello world'
    assert payload['level'] == 'INFO'
    assert payload['stream_id'] == 3
    assert payload['score'] == 2.5
    assert 'ignored' not in payload


def test_formatter_includes_exception_text():
    try:
        raise ValueError('boom')
    except ValueError:
        import sys
        record = _record()
        record.exc_info = sys.exc_info()

    assert 'boom' in json.loads(JSONFormatter().format(record))['exc']
