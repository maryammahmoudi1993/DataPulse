import os

from .settings import *  # noqa: F401,F403


def _csv(name):
    return [item.strip() for item in os.environ.get(name, '').split(',') if item.strip()]


DEBUG = False
SECRET_KEY = os.environ['SECRET_KEY']
ALLOWED_HOSTS = _csv('ALLOWED_HOSTS')

# Database: DATABASE_URL and static files (WhiteNoise) are handled in the base settings.

# HTTPS (the platform terminates TLS and forwards X-Forwarded-Proto)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r'^health/$', r'^readiness/$']
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Origins of the hosted frontend, when served from a different domain
CORS_ALLOWED_ORIGINS = _csv('CORS_ALLOWED_ORIGINS')
