from rest_framework.permissions import BasePermission


class HasAPIKeyScope(BasePermission):
    """Require the view's ``required_scope`` when authenticated with an API key.

    Requests authenticated by other means (JWT, session) pass through as long
    as the user is logged in; their access is governed by workspace membership.
    """

    required_scope = ''

    def has_permission(self, request, view):
        if not hasattr(request.auth, 'has_scope'):
            return bool(request.user and request.user.is_authenticated)
        return request.auth.has_scope(getattr(view, 'required_scope', self.required_scope))


class ReadStreamsPermission(HasAPIKeyScope):
    required_scope = 'read:streams'


class WriteDatapointsPermission(HasAPIKeyScope):
    required_scope = 'write:datapoints'


class ReadAlertsPermission(HasAPIKeyScope):
    required_scope = 'read:alerts'
