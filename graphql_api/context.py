from functools import cached_property

from graphql import GraphQLError

from graphql_api.auth import ANONYMOUS, principal_from_header


class GQLContext:
    """Per-operation context shared by HTTP requests and WebSocket sessions.

    HTTP reads the ``Authorization`` header. WebSocket sessions send the same
    value in the ``connection_init`` payload, which Strawberry stores in
    ``connection_params`` once the client has connected.
    """

    def __init__(self, request=None):
        self.request = request
        self.connection_params = None

    def _header(self):
        if self.connection_params:
            return self.connection_params.get('Authorization') or self.connection_params.get('authorization')
        if self.request is not None and hasattr(self.request, 'META'):
            return self.request.META.get('HTTP_AUTHORIZATION')
        return None

    @cached_property
    def principal(self):
        """Resolve credentials once per context. Performs DB queries (sync)."""
        header = self._header()
        return principal_from_header(header) if header else ANONYMOUS

    def require_auth(self):
        if not self.principal.is_authenticated:
            raise GraphQLError('Authentication required.', extensions={'code': 'UNAUTHENTICATED'})
        return self.principal

    def require_scope(self, scope):
        """Authenticated, and (for API keys) holding ``scope``."""
        principal = self.require_auth()
        if not principal.has_scope(scope):
            raise GraphQLError(f'API key lacks scope {scope}.', extensions={'code': 'FORBIDDEN'})
        return principal

    def require_user(self):
        """Authenticated as a person; API keys are read-only and refused here."""
        principal = self.require_auth()
        if principal.api_key is not None:
            raise GraphQLError('API keys cannot perform mutations.', extensions={'code': 'FORBIDDEN'})
        return principal
