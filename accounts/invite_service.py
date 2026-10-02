import logging
import smtplib
from email.message import EmailMessage

from django.conf import settings
from django.db import transaction

from .models import UserWorkspace, WorkspaceInvite

logger = logging.getLogger(__name__)


def create_invite(workspace, invited_by, email, role):
    """Create a pending invite and email it.

    Any earlier pending invite for the same email is marked expired.

    Args:
        workspace: Workspace the invitee will join.
        invited_by: User sending the invite.
        email: Invitee email address.
        role: One of the ``UserWorkspace`` role values.

    Returns:
        The new ``WorkspaceInvite``.

    Raises:
        ValueError: If the email already belongs to a member or the role is invalid.
    """
    if role not in dict(UserWorkspace.ROLE_CHOICES):
        raise ValueError(f'Invalid role: {role}')
    if UserWorkspace.objects.filter(workspace=workspace, user__email__iexact=email).exists():
        raise ValueError(f'{email} is already a member of this workspace.')

    with transaction.atomic():
        WorkspaceInvite.objects.filter(
            workspace=workspace, email=email, status=WorkspaceInvite.STATUS_PENDING,
        ).update(status=WorkspaceInvite.STATUS_EXPIRED)
        invite = WorkspaceInvite.objects.create(
            workspace=workspace, invited_by=invited_by, email=email, role=role,
        )
    _send_invite_email(invite)
    return invite


def accept_invite(token, user):
    """Accept an invite and create (or update) the user's membership.

    Args:
        token: Invite token.
        user: User accepting the invite.

    Returns:
        The user's ``UserWorkspace`` membership.

    Raises:
        ValueError: If the token is unknown, already used, or expired.
    """
    with transaction.atomic():
        try:
            invite = WorkspaceInvite.objects.select_related('workspace').select_for_update().get(
                token=token, status=WorkspaceInvite.STATUS_PENDING,
            )
        except WorkspaceInvite.DoesNotExist:
            raise ValueError('Invalid or already-used invite token.')

        if invite.is_expired:
            invite.status = WorkspaceInvite.STATUS_EXPIRED
            invite.save(update_fields=['status'])
            expired = True
        else:
            expired = False
            membership, created = UserWorkspace.objects.get_or_create(
                user=user, workspace=invite.workspace, defaults={'role': invite.role},
            )
            if not created:
                membership.role = invite.role
                membership.save(update_fields=['role'])
            invite.status = WorkspaceInvite.STATUS_ACCEPTED
            invite.accepted_by = user
            invite.save(update_fields=['status', 'accepted_by'])

    if expired:
        raise ValueError('This invite has expired.')

    logger.info('Invite accepted', extra={
        'workspace_id': invite.workspace_id, 'user_id': user.id, 'role': invite.role,
    })
    return membership


def _send_invite_email(invite):
    """Email the invite link; skipped (with a warning) when SMTP is not configured."""
    smtp_user = getattr(settings, 'SMTP_USER', '')
    if not smtp_user:
        logger.warning('SMTP not configured - invite email not sent', extra={'invite_id': invite.id})
        return

    base = getattr(settings, 'INVITE_BASE_URL', 'http://localhost:8000')
    ttl = getattr(settings, 'INVITE_TOKEN_TTL_DAYS', 7)
    msg = EmailMessage()
    msg['Subject'] = f'You are invited to join {invite.workspace.name} on DataPulse'
    msg['From'] = getattr(settings, 'SMTP_FROM', smtp_user)
    msg['To'] = invite.email
    msg.set_content(
        f'You have been invited to join "{invite.workspace.name}" as {invite.role}.\n\n'
        f'Accept your invite here:\n{base}/api/invites/{invite.token}/accept/\n\n'
        f'This link expires in {ttl} days.'
    )
    try:
        with smtplib.SMTP(getattr(settings, 'SMTP_HOST', 'smtp.gmail.com'), getattr(settings, 'SMTP_PORT', 587)) as s:
            s.starttls()
            s.login(smtp_user, getattr(settings, 'SMTP_PASSWORD', ''))
            s.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        logger.error('Invite email failed', extra={'invite_id': invite.id, 'exc': str(exc)})
