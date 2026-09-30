from django.conf import settings
from django.db import models


class UserWorkspace(models.Model):
    """Membership of a user in a workspace, with a role."""

    ROLE_OWNER = 'OWNER'
    ROLE_MEMBER = 'MEMBER'
    ROLE_VIEWER = 'VIEWER'
    ROLE_CHOICES = [
        (ROLE_OWNER, 'Owner'),
        (ROLE_MEMBER, 'Member'),
        (ROLE_VIEWER, 'Viewer'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='workspace_memberships',
    )
    workspace = models.ForeignKey(
        'streams.Workspace',
        on_delete=models.CASCADE,
        related_name='memberships',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'workspace')
        ordering = ['joined_at']

    def __str__(self):
        return f'{self.user.username} -> {self.workspace.slug} ({self.role})'
