from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from streams.models import Workspace

from accounts.models import UserWorkspace, WorkspaceInvite

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    workspace = serializers.SlugField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'workspace']

    def validate_workspace(self, value):
        if Workspace.objects.filter(slug=value).exists():
            raise serializers.ValidationError('Workspace slug already taken.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Create the user together with a workspace they own.

        Args:
            validated_data: Validated username, email, password and workspace slug.

        Returns:
            The new user.
        """
        slug = validated_data.pop('workspace')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        workspace = Workspace.objects.create(name=slug.capitalize(), slug=slug, owner=user)
        UserWorkspace.objects.create(user=user, workspace=workspace, role=UserWorkspace.ROLE_OWNER)
        return user


class UserSerializer(serializers.ModelSerializer):
    workspaces = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'workspaces']

    def get_workspaces(self, obj):
        memberships = obj.workspace_memberships.select_related('workspace')
        return [
            {'id': m.workspace_id, 'slug': m.workspace.slug, 'role': m.role}
            for m in memberships
        ]


class WorkspaceInviteSerializer(serializers.ModelSerializer):
    invited_by_username = serializers.CharField(source='invited_by.username', read_only=True, default=None)

    class Meta:
        model = WorkspaceInvite
        fields = ['id', 'email', 'role', 'status', 'expires_at', 'invited_by_username', 'created_at']
        read_only_fields = ['status', 'expires_at', 'invited_by_username', 'created_at']


class MemberSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    user_id = serializers.IntegerField(source='user.id', read_only=True)

    class Meta:
        model = UserWorkspace
        fields = ['user_id', 'username', 'email', 'role', 'joined_at']
        read_only_fields = ['user_id', 'username', 'email', 'joined_at']
