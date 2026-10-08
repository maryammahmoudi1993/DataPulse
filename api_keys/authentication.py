import logging

from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .models import APIKey, hash_key

logger = logging.getLogger(__name__)


class APIKeyAuthentication(BaseAuthentication):
    """Authenticate ``Authorization: Api-Key dp_live_xxx`` requests.

    ``request.auth`` is set to the ``APIKey`` so views can check scopes.
    Keys are only honoured on views that opt in with ``api_key_enabled = True``;
    every other endpoint rejects them, so a narrowly scoped key can never act
    with the full privileges of the user who created it.
    """

    keyword = 'Api-Key'

    def authenticate(self, request):
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if not header.startswith(f'{self.keyword} '):
            return None  # not our scheme - let other backends try

        raw_key = header[len(self.keyword) + 1:].strip()
        if not raw_key:
            return None

        try:
            key = APIKey.objects.select_related('workspace__owner', 'created_by').get(
                key_hash=hash_key(raw_key), is_active=True,
            )
        except APIKey.DoesNotExist:
            raise AuthenticationFailed('Invalid API key.')

        if key.expires_at and key.expires_at < timezone.now():
            raise AuthenticationFailed('API key has expired.')

        view = getattr(request, 'parser_context', {}).get('view')
        if not getattr(view, 'api_key_enabled', False):
            raise AuthenticationFailed('API keys cannot be used on this endpoint.')

        user = key.created_by or key.workspace.owner
        if user is None or not user.is_active:
            raise AuthenticationFailed('API key has no active owner.')

        APIKey.objects.filter(pk=key.pk).update(last_used=timezone.now())
        logger.info('API key authenticated', extra={'key_prefix': key.prefix, 'workspace_id': key.workspace_id})
        return user, key

    def authenticate_header(self, request):
        return self.keyword
