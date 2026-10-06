import os
import sys

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from streams.models import Stream

DEFAULT_SECRET_KEYS = (
    'change-me-in-production',
    'django-insecure-change-me-in-production',
    'docker-dev-secret-change-in-production',
    'ci-secret-key-not-for-production',
)


class Command(BaseCommand):
    help = 'Validates production deployment readiness. Exits 1 if any check fails.'

    def _marks(self):
        """Return pass/fail symbols, falling back to ASCII on consoles that cannot print them."""
        encoding = getattr(self.stdout._out, 'encoding', None) or 'utf-8'
        try:
            '✓✗'.encode(encoding)
        except (UnicodeEncodeError, LookupError):
            return 'OK', 'XX'
        return '✓', '✗'

    def handle(self, *args, **options):
        passed = 0
        failed = 0
        ok_mark, fail_mark = self._marks()

        def check(name, condition, fix=''):
            nonlocal passed, failed
            if condition:
                passed += 1
                self.stdout.write(self.style.SUCCESS(f'  {ok_mark}  {name}'))
            else:
                failed += 1
                msg = f'  {fail_mark}  {name}'
                if fix:
                    msg += f'\n       Fix: {fix}'
                self.stdout.write(self.style.ERROR(msg))

        self.stdout.write('\n=== DataPulse production readiness check ===\n')

        self.stdout.write('Security:')
        check('DEBUG is False', not settings.DEBUG, 'Set DEBUG=False in environment')
        check('SECRET_KEY is not the default',
              settings.SECRET_KEY not in DEFAULT_SECRET_KEYS,
              'Generate a new SECRET_KEY')
        check('ALLOWED_HOSTS is not empty', bool(settings.ALLOWED_HOSTS), 'Set ALLOWED_HOSTS=yourdomain.com')
        check('SECURE_SSL_REDIRECT is True',
              getattr(settings, 'SECURE_SSL_REDIRECT', False),
              'Enable in settings_prod.py or set env var')
        check('SESSION_COOKIE_SECURE is True',
              getattr(settings, 'SESSION_COOKIE_SECURE', False),
              'Enable in settings_prod.py')

        self.stdout.write('\nInfrastructure:')
        db_ok = False
        try:
            connection.ensure_connection()
            db_ok = True
            check('Database reachable', True)
        except Exception as exc:  # noqa: BLE001 - report any connection failure
            check('Database reachable', False, str(exc))

        try:
            import redis
            redis.from_url(settings.REDIS_URL, socket_connect_timeout=2).ping()
            check('Redis reachable', True)
        except Exception as exc:  # noqa: BLE001
            check('Redis reachable', False, str(exc))

        try:
            cache.set('_prod_check', 1, 5)
            check('Cache writable', cache.get('_prod_check') == 1, 'Check CACHES and Redis connectivity')
        except Exception as exc:  # noqa: BLE001
            check('Cache writable', False, str(exc))

        self.stdout.write('\nMigrations:')
        if db_ok:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            check('No pending migrations', not plan, f'Run: python manage.py migrate ({len(plan)} pending)')
        else:
            check('No pending migrations', False, 'Database unreachable')

        self.stdout.write('\nConfiguration:')
        check('SENTRY_DSN configured', bool(settings.SENTRY_DSN), 'Set SENTRY_DSN for error tracking')
        check('SMTP configured',
              bool(getattr(settings, 'SMTP_USER', '')),
              'Set SMTP_USER + SMTP_PASSWORD for alert digests and invites')
        check('STATIC_ROOT exists',
              os.path.isdir(str(settings.STATIC_ROOT)),
              'Run: python manage.py collectstatic')

        self.stdout.write('\nContent:')
        if db_ok:
            check('At least one active stream',
                  Stream.objects.filter(status=Stream.STATUS_ACTIVE).exists(),
                  'Run: python manage.py seed_demo')
            check('Superuser exists',
                  User.objects.filter(is_superuser=True).exists(),
                  'Run: python manage.py createsuperuser')
        else:
            check('At least one active stream', False, 'Database unreachable')
            check('Superuser exists', False, 'Database unreachable')

        failed_text = self.style.ERROR(f'{failed} failed') if failed else '0 failed'
        self.stdout.write(f'\n{passed + failed} checks: {self.style.SUCCESS(f"{passed} passed")}, {failed_text}\n')

        if failed:
            sys.exit(1)
