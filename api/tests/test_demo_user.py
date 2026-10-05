from django.contrib.auth.models import User
from django.core.management import call_command

from accounts.models import UserWorkspace


def test_seed_demo_creates_demo_user(db):
    call_command('seed_demo', '--points', '10', '--flush')
    user = User.objects.get(username='demo')
    assert user.check_password('demodemo1')


def test_demo_user_is_workspace_owner(db):
    call_command('seed_demo', '--points', '10', '--flush')
    assert UserWorkspace.objects.filter(
        user__username='demo',
        role=UserWorkspace.ROLE_OWNER,
    ).exists()


def test_seed_demo_idempotent_with_user(db):
    call_command('seed_demo', '--points', '10', '--flush')
    call_command('seed_demo', '--points', '10')
    assert User.objects.filter(username='demo').count() == 1
    assert UserWorkspace.objects.filter(user__username='demo').count() == 1
