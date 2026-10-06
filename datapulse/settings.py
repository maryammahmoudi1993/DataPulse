from datetime import timedelta
from pathlib import Path

import environ
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.redis import RedisIntegration

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='django-insecure-change-me-in-production')

DEBUG = env.bool('DEBUG', default=True)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])


INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    'django_celery_beat',
    'django_celery_results',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'streams',
    'ingestion',
    'detection',
    'sources',
    'api',
    'alerts',
    'realtime',
    'accounts',
    'exports',
    'reports',
    'audit',
    'drf_spectacular',
    'integrations',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'datapulse.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'datapulse.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'datapulse.wsgi.application'


DATABASES = {
    'default': env.db('DATABASE_URL', default='sqlite:///' + str(BASE_DIR / 'db.sqlite3')),
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/min',
        'user': '200/min',
        'workspace': '1000/hour',
    },
}


REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
DJANGO_CELERY_RESULTS_TASK_ID_MAX_LENGTH = 191
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = env.bool('CELERY_TASK_ALWAYS_EAGER', default=True)
CELERY_TASK_EAGER_PROPAGATES = True

CELERY_BEAT_SCHEDULE = {
    'poll-all-active-streams': {
        'task': 'ingestion.tasks.poll_all_active_streams',
        'schedule': 5.0,
    },
    'cleanup-old-datapoints': {
        'task': 'ingestion.tasks.cleanup_old_datapoints',
        'schedule': 3600 * 24,
    },
    'send-alert-digest': {
        'task': 'reports.tasks.send_daily_alert_digest',
        'schedule': 3600 * 24,
    },
    'cleanup-stale-exports': {
        'task': 'exports.tasks.cleanup_stale_exports',
        'schedule': 3600 * 6,
    },
}


ASGI_APPLICATION = 'datapulse.asgi.application'

CHANNEL_LAYER_BACKEND = env('CHANNEL_LAYER_BACKEND', default='redis')
if CHANNEL_LAYER_BACKEND == 'memory':
    CHANNEL_LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {'hosts': [REDIS_URL]},
        },
    }

ALERT_DEDUP_WINDOW_MINUTES = env.int('ALERT_DEDUP_WINDOW_MINUTES', default=5)
ALERT_WEBHOOK_TIMEOUT_SECONDS = env.int('ALERT_WEBHOOK_TIMEOUT_SECONDS', default=5)

LSTM_MODEL_DIR = env('LSTM_MODEL_DIR', default=str(BASE_DIR / 'media' / 'lstm_models'))

# Prometheus
PROMETHEUS_METRICS_EXPORT_PORT = 8001
PROMETHEUS_METRICS_EXPORT_HOST = '0.0.0.0'

# Data export
EXPORT_ROOT = env('EXPORT_ROOT', default=str(BASE_DIR / 'media' / 'exports'))
EXPORT_TTL_HOURS = env.int('EXPORT_TTL_HOURS', default=24)

# Alert digest
SMTP_HOST = env('SMTP_HOST', default='smtp.gmail.com')
SMTP_PORT = env.int('SMTP_PORT', default=587)
SMTP_USER = env('SMTP_USER', default='')
SMTP_PASSWORD = env('SMTP_PASSWORD', default='')
SMTP_FROM = env('SMTP_FROM', default='noreply@datapulse.local')

# Workspace invites
INVITE_TOKEN_TTL_DAYS = env.int('INVITE_TOKEN_TTL_DAYS', default=7)
INVITE_BASE_URL = env('INVITE_BASE_URL', default='http://localhost:3000')

SPECTACULAR_SETTINGS = {
    'TITLE': 'DataPulse API',
    'DESCRIPTION': 'Real-time anomaly detection and alerting platform.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'ENUM_NAME_OVERRIDES': {'SeverityEnum': 'alerts.models.Alert.SEVERITY_CHOICES'},
    'TAGS': [
        {'name': 'auth', 'description': 'JWT authentication'},
        {'name': 'streams', 'description': 'Stream management'},
        {'name': 'alerts', 'description': 'Anomaly alerts'},
        {'name': 'integrations', 'description': 'Slack and PagerDuty'},
        {'name': 'audit', 'description': 'Audit log'},
        {'name': 'exports', 'description': 'CSV data exports'},
    ],
}

DEMO_WORKSPACE_SLUG = 'demo'
DEMO_PUBLIC_ACCESS = env.bool('DEMO_PUBLIC_ACCESS', default=False)


SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {'()': 'datapulse.logging_config.JSONFormatter'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'json'},
    },
    'loggers': {
        name: {'handlers': ['console'], 'level': 'INFO', 'propagate': False}
        for name in ('datapulse', 'ingestion', 'detection', 'alerts', 'api', 'accounts', 'exports', 'reports', 'integrations')
    },
    'root': {'handlers': ['console'], 'level': 'WARNING'},
}


# Sentry
SENTRY_DSN = env('SENTRY_DSN', default='')

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(transaction_style='url'),
            CeleryIntegration(monitor_beat_tasks=True),
            RedisIntegration(),
        ],
        traces_sample_rate=env.float('SENTRY_TRACES_SAMPLE_RATE', default=0.1),
        send_default_pii=False,  # never send user PII to Sentry
        environment=env('ENVIRONMENT', default='development'),
    )

# Redis cache
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 2,
            'SOCKET_TIMEOUT': 2,
            'IGNORE_EXCEPTIONS': True,  # cache miss on Redis error: never break a request
        },
        'TIMEOUT': 300,  # 5 minutes default
    }
}

STREAM_LIST_CACHE_TTL = env.int('STREAM_LIST_CACHE_TTL', default=60)  # seconds
ALERT_LIST_CACHE_TTL = env.int('ALERT_LIST_CACHE_TTL', default=30)
STREAM_STATS_CACHE_TTL = env.int('STREAM_STATS_CACHE_TTL', default=120)
