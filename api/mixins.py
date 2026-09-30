from streams.models import Workspace


class WorkspaceScopedMixin:
    """Restricts a viewset to the workspaces the requesting user belongs to."""

    def get_accessible_workspaces(self):
        """Return the workspaces visible to ``request.user``."""
        return Workspace.accessible_to(self.request.user)

    def get_user_workspace_ids(self):
        """Return the ids of the workspaces visible to ``request.user``."""
        return list(self.get_accessible_workspaces().values_list('pk', flat=True))
