from graphql import GraphQLError

from accounts.models import UserWorkspace
from streams.models import Workspace


def can_write(user, workspace_id):
    """True when ``user`` may change data in the workspace (OWNER or MEMBER, not VIEWER)."""
    if Workspace.objects.filter(pk=workspace_id, owner=user).exists():
        return True
    if Workspace.objects.filter(pk=workspace_id, members=user).exists():
        return True  # legacy M2M members have no role and count as members
    return UserWorkspace.objects.filter(
        user=user, workspace_id=workspace_id,
        role__in=[UserWorkspace.ROLE_OWNER, UserWorkspace.ROLE_MEMBER],
    ).exists()


def require_member_or_above(principal, workspace_id):
    """Raise unless the caller may mutate data in the workspace; VIEWERs cannot."""
    if not can_write(principal.user, workspace_id):
        raise GraphQLError(
            'Insufficient permissions: MEMBER or OWNER role required.',
            extensions={'code': 'FORBIDDEN'},
        )
