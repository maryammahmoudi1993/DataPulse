import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


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


def _new_invite_token():
    """Return a random 32-character hex token."""
    return uuid.uuid4().hex


class WorkspaceInvite(models.Model):
    """A single-use, expiring invitation to join a workspace."""

    STATUS_PENDING = 'PENDING'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    workspace = models.ForeignKey('streams.Workspace', on_delete=models.CASCADE, related_name='invites')
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sent_invites',
    )
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=UserWorkspace.ROLE_CHOICES, default=UserWorkspace.ROLE_MEMBER)
    token = models.CharField(max_length=64, unique=True, default=_new_invite_token)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    expires_at = models.DateTimeField()
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_invites',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['workspace', 'email'],
                condition=models.Q(status='PENDING'),
                name='unique_pending_invite_per_email',
            ),
        ]

    def __str__(self):
        return f'Invite[{self.status}] {self.email} -> {self.workspace.slug}'

    @property
    def is_expired(self):
        """Whether the invite is past its expiry time."""
        return timezone.now() > self.expires_at

    def save(self, *args, **kwargs):
        if not self.expires_at:
            ttl = getattr(settings, 'INVITE_TOKEN_TTL_DAYS', 7)
            self.expires_at = timezone.now() + timedelta(days=ttl)
        super().save(*args, **kwargs)
