import hashlib
import secrets

from django.conf import settings
from django.db import models

from streams.models import Workspace


def _generate_key() -> str:
    """Return a secure random key suffix. Never stored in plaintext."""
    return secrets.token_hex(32)


def hash_key(raw: str) -> str:
    """Return the SHA-256 hex digest under which a raw key is stored."""
    return hashlib.sha256(raw.encode()).hexdigest()


class APIKey(models.Model):
    """One row per issued API key.

    Only the SHA-256 hash is stored. The full key is shown once on creation
    and never again.
    """

    SCOPE_READ_STREAMS = 'read:streams'
    SCOPE_WRITE_POINTS = 'write:datapoints'
    SCOPE_READ_ALERTS = 'read:alerts'
    SCOPE_CHOICES = [
        (SCOPE_READ_STREAMS, 'Read streams and data points'),
        (SCOPE_WRITE_POINTS, 'Ingest data points'),
        (SCOPE_READ_ALERTS, 'Read alerts'),
    ]

    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='api_keys')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='api_keys',
    )
    name = models.CharField(max_length=100, help_text='Human-readable label for this key.')
    prefix = models.CharField(max_length=12, db_index=True, help_text='First 12 chars of the raw key for display.')
    key_hash = models.CharField(max_length=64, unique=True)
    scopes = models.JSONField(default=list, help_text='List of scope strings this key is allowed.')
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['workspace', 'is_active'])]

    def __str__(self):
        return f'APIKey[{self.prefix}…] {self.name} workspace={self.workspace_id}'

    @classmethod
    def create(cls, workspace, created_by, name, scopes, expires_at=None):
        """Create a key and return ``(instance, raw_key)``.

        Args:
            workspace: Workspace the key belongs to.
            created_by: User issuing the key.
            name: Human-readable label.
            scopes: List of scope strings granted to the key.
            expires_at: Optional expiry datetime.

        Returns:
            Tuple of the saved instance and the full ``dp_live_...`` key,
            which is the only time the plaintext exists.
        """
        raw_key = f'{settings.API_KEY_PREFIX}{_generate_key()}'
        instance = cls.objects.create(
            workspace=workspace,
            created_by=created_by,
            name=name,
            prefix=raw_key[:12],
            key_hash=hash_key(raw_key),
            scopes=list(scopes),
            expires_at=expires_at,
        )
        return instance, raw_key

    def verify(self, raw_key: str) -> bool:
        return secrets.compare_digest(hash_key(raw_key), self.key_hash)

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes
