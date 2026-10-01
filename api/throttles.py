from rest_framework.throttling import UserRateThrottle


class WorkspaceRateThrottle(UserRateThrottle):
    """Per-user limit on write operations, configured as the ``workspace`` rate."""

    scope = 'workspace'
