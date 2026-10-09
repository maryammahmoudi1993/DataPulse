"""Authentication for the GraphQL endpoint (HTTP and WebSocket).

Accepts the same credentials as the REST API: ``Bearer <JWT>`` and
``Api-Key <key>``. API keys are limited to read-only queries and
subscriptions, restricted to their own workspace and scopes.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken

from api_keys.models import APIKey, hash_key
from streams.models import Workspace

logger = logging.getLogger(__name__)


@dataclass
class Principal:
    """Who is calling: a user, optionally narrowed by an API key."""

    user: object
    api_key: Optional[APIKey] = None

    @property
    def is_authenticated(self):
        return bool(self.user and self.user.is_authenticated)

    def workspaces(self):
        """Workspaces this caller may see; an API key sees only its own."""
        qs = Workspace.accessible_to(self.user)
        if self.api_key is not None:
            qs = qs.filter(pk=self.api_key.workspace_id)
        return qs

    def has_scope(self, scope):
        """JWT/session callers pass; API keys need the scope granted."""
        return self.api_key is None or self.api_key.has_scope(scope)


ANONYMOUS = Principal(user=AnonymousUser())


def principal_from_header(header, fallback_user=None):
    """Resolve an ``Authorization`` header value to a ``Principal``.

    Invalid or expired credentials yield an anonymous principal, never a
    silent fallback to a session user, so a bad token cannot be masked.
    """
    header = (header or '').strip()
    if not header:
        if fallback_user is not None and fallback_user.is_authenticated:
            return Principal(user=fallback_user)
        return ANONYMOUS

    scheme, _, credential = header.partition(' ')
    credential = credential.strip()
    if scheme == 'Bearer' and credential:
        return _from_jwt(credential)
    if scheme == 'Api-Key' and credential:
        return _from_api_key(credential)
    return ANONYMOUS


def _from_jwt(raw):
    from django.contrib.auth import get_user_model

    try:
        user_id = AccessToken(raw)['user_id']
    except (TokenError, KeyError):
        return ANONYMOUS
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    return Principal(user=user) if user else ANONYMOUS


def _from_api_key(raw):
    key = APIKey.objects.select_related('workspace__owner', 'created_by').filter(
        key_hash=hash_key(raw), is_active=True,
    ).first()
    if key is None or (key.expires_at and key.expires_at < timezone.now()):
        return ANONYMOUS
    user = key.created_by or key.workspace.owner
    if user is None or not user.is_active:
        return ANONYMOUS
    APIKey.objects.filter(pk=key.pk).update(last_used=timezone.now())
    logger.info('API key authenticated (GraphQL)', extra={'key_prefix': key.prefix})
    return Principal(user=user, api_key=key)
