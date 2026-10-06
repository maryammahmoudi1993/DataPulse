from io import StringIO
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from streams.models import Stream, Workspace

User = get_user_model()


@pytest.fixture
def ready_env(db, settings, tmp_path):
    """A fully production-ready configuration with Redis mocked out."""
    settings.DEBUG = False
    settings.SECRET_KEY = 'a-real-production-secret'
    settings.ALLOWED_HOSTS = ['datapulse.example.com']
    settings.SECURE_SSL_REDIRECT = True
    settings.SESSION_COOKIE_SECURE = True
    settings.SENTRY_DSN = 'https://key@example.ingest.sentry.io/1'
    settings.SMTP_USER = 'mailer@example.com'
    settings.STATIC_ROOT = str(tmp_path)
    owner = User.objects.create_superuser('admin', 'admin@example.com', 'x')
    workspace = Workspace.objects.create(name='W', slug='w', owner=owner)
    Stream.objects.create(workspace=workspace, name='S', source_type=Stream.SOURCE_SIMULATOR)
    with mock.patch('redis.from_url'):
        yield settings


def run_check():
    out = StringIO()
    try:
        call_command('production_check', stdout=out)
        code = 0
    except SystemExit as exc:
        code = exc.code
    return code, out.getvalue()


def test_production_check_passes_in_test_env(ready_env):
    code, output = run_check()

    assert code == 0, output
    assert '0 failed' in output


def test_production_check_fails_on_debug_true(ready_env):
    ready_env.DEBUG = True

    code, output = run_check()

    assert code == 1
    assert '✗' in output or 'XX' in output
    assert 'DEBUG is False' in output


def test_production_check_fails_on_pending_migration(ready_env):
    with mock.patch(
        'datapulse.management.commands.production_check.MigrationExecutor'
    ) as executor:
        executor.return_value.migration_plan.return_value = [('app.0001', False)]
        code, output = run_check()

    assert code == 1
    assert '1 pending' in output


def test_production_check_reports_no_active_stream(ready_env):
    Stream.objects.all().delete()

    code, output = run_check()

    assert code == 1
    assert 'At least one active stream' in output
    assert 'seed_demo' in output


def test_production_check_fails_on_default_secret_key(ready_env):
    ready_env.SECRET_KEY = 'django-insecure-change-me-in-production'

    code, _ = run_check()

    assert code == 1
