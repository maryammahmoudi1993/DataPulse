import os

from django.conf import settings
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from celery.result import AsyncResult
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.invite_service import accept_invite, create_invite
from accounts.models import UserWorkspace, WorkspaceInvite
from accounts.serializers import MemberSerializer, WorkspaceInviteSerializer
from alerts.models import Alert, WebhookEndpoint
from streams.models import Stream, Workspace

from api.mixins import WorkspaceScopedMixin
from api.pagination import TimestampCursorPagination
from api.serializers import (
    AlertSerializer,
    AuditEventSerializer,
    DataPointSerializer,
    StreamSerializer,
    WebhookEndpointSerializer,
    WorkspaceSerializer,
)
from api.throttles import WorkspaceRateThrottle
from audit.models import AuditEvent
from audit.services import get_client_ip, log_event
from exports.models import ExportJob
from exports.tasks import run_export
from ingestion.models import DataPoint


class IsAuthenticatedOrPublicDemo(permissions.BasePermission):
    """Authenticated users get full access.

    When ``DEMO_PUBLIC_ACCESS`` is on, anonymous visitors may also read and
    PATCH resources; the querysets restrict them to the demo workspace.
    """

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return True
        if not getattr(settings, 'DEMO_PUBLIC_ACCESS', False):
            return False
        return request.method in permissions.SAFE_METHODS or request.method == 'PATCH'


class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer

    def get_queryset(self):
        return Workspace.accessible_to(self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class StreamViewSet(WorkspaceScopedMixin, viewsets.ModelViewSet):
    serializer_class = StreamSerializer
    permission_classes = [IsAuthenticatedOrPublicDemo]

    def get_queryset(self):
        return Stream.objects.filter(workspace_id__in=self.get_user_workspace_ids())

    def get_throttles(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [WorkspaceRateThrottle()]
        return super().get_throttles()

    def perform_create(self, serializer):
        workspace = serializer.validated_data.get('workspace')
        get_object_or_404(self.get_accessible_workspaces(), pk=workspace.pk)
        stream = serializer.save()
        log_event(actor=self.request.user, workspace=stream.workspace, action='STREAM_CREATED',
                  stream=stream, ip_address=get_client_ip(self.request))

    def perform_destroy(self, instance):
        log_event(actor=self.request.user, workspace=instance.workspace, action='STREAM_DELETED',
                  metadata={'stream_name': instance.name}, ip_address=get_client_ip(self.request))
        instance.delete()

    @action(detail=True, methods=['post'], url_path='train-lstm')
    def train_lstm(self, request, *args, **kwargs):
        """Queue LSTM training for the stream and return the task id."""
        stream = self.get_object()
        if stream.detector_type != Stream.DETECTOR_LSTM:
            return Response(
                {'detail': 'Stream detector_type must be LSTM.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from detection.tasks import train_lstm_for_stream
        task = train_lstm_for_stream.delay(stream.id)
        log_event(actor=request.user, workspace=stream.workspace, action='LSTM_TRAINING_TRIGGERED',
                  stream=stream, ip_address=get_client_ip(request))
        return Response({'task_id': task.id}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'], url_path='training-status')
    def training_status(self, request, *args, **kwargs):
        """Report the state of a training task started via ``train-lstm``."""
        self.get_object()
        task_id = request.query_params.get('task_id')
        if not task_id:
            return Response(
                {'detail': 'task_id query param required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        result = AsyncResult(task_id)
        return Response({
            'state': result.state,
            'meta': result.info if result.state == 'PROGRESS' else {},
            'result': result.result if result.state == 'SUCCESS' else None,
        })

    @action(detail=True, methods=['post'], url_path='compare-detectors')
    def compare_detectors(self, request, *args, **kwargs):
        """Replay stored data through two detectors and report their agreement."""
        stream = self.get_object()
        type_a = request.data.get('a')
        type_b = request.data.get('b')
        valid = [Stream.DETECTOR_ZSCORE, Stream.DETECTOR_IQR, Stream.DETECTOR_LSTM]

        if type_a not in valid or type_b not in valid:
            return Response(
                {'detail': f'detector must be one of {valid}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if type_a == type_b:
            return Response(
                {'detail': 'a and b must be different detectors.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from detection.comparison import compare_detectors as run_comparison
        result = run_comparison(stream, type_a, type_b)
        if 'error' in result:
            return Response(result, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(result)

    @action(detail=True, methods=['post'], url_path='export')
    def export(self, request, *args, **kwargs):
        """Queue a CSV export of the stream's data points or alerts."""
        stream = self.get_object()
        export_type = request.data.get('type', ExportJob.TYPE_DATAPOINTS)
        if export_type not in (ExportJob.TYPE_DATAPOINTS, ExportJob.TYPE_ALERTS):
            return Response(
                {'detail': 'type must be DATAPOINTS or ALERTS.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        job = ExportJob.objects.create(stream=stream, requested_by=request.user, export_type=export_type)
        run_export.delay(job.id)
        log_event(actor=request.user, workspace=stream.workspace, action='EXPORT_REQUESTED',
                  stream=stream, metadata={'export_type': export_type}, ip_address=get_client_ip(request))
        return Response({'job_id': job.id, 'status': job.status}, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=['get'], url_path=r'export/(?P<job_id>[0-9]+)')
    def export_status(self, request, job_id=None, *args, **kwargs):
        """Report the state of an export job and, once done, its download URL."""
        stream = self.get_object()
        try:
            job = ExportJob.objects.get(pk=job_id, stream=stream)
        except ExportJob.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = {
            'job_id': job.id,
            'status': job.status,
            'export_type': job.export_type,
            'row_count': job.row_count,
            'created_at': job.created_at.isoformat(),
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        }
        if job.status == ExportJob.STATUS_DONE:
            data['download_url'] = f'/api/streams/{stream.id}/export/{job.id}/download/'
        return Response(data)

    @action(detail=True, methods=['get'], url_path=r'export/(?P<job_id>[0-9]+)/download')
    def export_download(self, request, job_id=None, *args, **kwargs):
        """Stream the finished CSV file."""
        stream = self.get_object()
        try:
            job = ExportJob.objects.get(pk=job_id, stream=stream, status=ExportJob.STATUS_DONE)
        except ExportJob.DoesNotExist:
            return Response(
                {'detail': 'Export not ready or not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not os.path.exists(job.file_path):
            return Response({'detail': 'File no longer available.'}, status=status.HTTP_410_GONE)
        return FileResponse(
            open(job.file_path, 'rb'),
            as_attachment=True,
            filename=f'stream_{stream.id}_{job.export_type.lower()}.csv',
        )

    @action(detail=True, methods=['post'])
    def pause(self, request, *args, **kwargs):
        stream = self.get_object()
        stream.status = Stream.STATUS_PAUSED
        stream.save(update_fields=['status'])
        log_event(actor=request.user, workspace=stream.workspace, action='STREAM_PAUSED',
                  stream=stream, ip_address=get_client_ip(request))
        return Response(StreamSerializer(stream).data)

    @action(detail=True, methods=['post'])
    def resume(self, request, *args, **kwargs):
        stream = self.get_object()
        stream.status = Stream.STATUS_ACTIVE
        stream.save(update_fields=['status'])
        log_event(actor=request.user, workspace=stream.workspace, action='STREAM_RESUMED',
                  stream=stream, ip_address=get_client_ip(request))
        return Response(StreamSerializer(stream).data)


class DataPointViewSet(viewsets.ReadOnlyModelViewSet):
    """Data points of one stream.

    Cursor-paginated, newest first. The legacy ``limit`` query parameter
    still returns a plain list of the newest points.
    """

    serializer_class = DataPointSerializer
    pagination_class = TimestampCursorPagination

    def get_queryset(self):
        stream_pk = self.kwargs.get('stream_pk')
        return DataPoint.objects.filter(
            stream_id=stream_pk,
            stream__workspace__in=Workspace.accessible_to(self.request.user),
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        limit = request.query_params.get('limit', '')
        if limit.isdigit():
            return Response(self.get_serializer(queryset[:int(limit)], many=True).data)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    """Alerts of one stream, filterable by ``severity`` and ``status``."""

    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticatedOrPublicDemo]

    def get_queryset(self):
        queryset = Alert.objects.filter(
            stream_id=self.kwargs.get('stream_pk'),
            stream__workspace__in=Workspace.accessible_to(self.request.user),
        )
        severity = self.request.query_params.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity.upper())
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status.upper())
        return queryset

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def acknowledge(self, request, *args, **kwargs):
        alert = self.get_object()
        alert.status = Alert.STATUS_ACKNOWLEDGED
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at'])
        log_event(actor=request.user, workspace=alert.stream.workspace, action='ALERT_ACKNOWLEDGED',
                  stream=alert.stream, metadata={'alert_id': alert.id}, ip_address=get_client_ip(request))
        return Response(AlertSerializer(alert).data)


class WebhookEndpointViewSet(viewsets.ModelViewSet):
    serializer_class = WebhookEndpointSerializer

    def get_queryset(self):
        return WebhookEndpoint.objects.filter(workspace__in=Workspace.accessible_to(self.request.user))

    def perform_create(self, serializer):
        workspace = serializer.validated_data.get('workspace')
        get_object_or_404(Workspace.accessible_to(self.request.user), pk=workspace.pk)
        serializer.save()
        log_event(actor=self.request.user, workspace=workspace, action='WEBHOOK_CREATED',
                  metadata={'url': serializer.validated_data['url']}, ip_address=get_client_ip(self.request))

    def perform_destroy(self, instance):
        log_event(actor=self.request.user, workspace=instance.workspace, action='WEBHOOK_DELETED',
                  metadata={'webhook_id': instance.pk}, ip_address=get_client_ip(self.request))
        instance.delete()


class WorkspaceAdminMixin(WorkspaceScopedMixin):
    """Workspace lookup and owner check shared by the nested workspace viewsets."""

    permission_classes = [permissions.IsAuthenticated]

    def _get_workspace(self, workspace_pk):
        """Return the accessible workspace ``workspace_pk`` or raise 404."""
        if not str(workspace_pk).isdigit():
            raise NotFound
        return get_object_or_404(self.get_accessible_workspaces(), pk=workspace_pk)

    def _require_owner(self, workspace, user, message):
        """Raise 403 unless ``user`` owns ``workspace``."""
        is_owner = UserWorkspace.objects.filter(
            workspace=workspace, user=user, role=UserWorkspace.ROLE_OWNER,
        ).exists()
        if not is_owner:
            raise PermissionDenied(message)


def _member_lookup(workspace, pk):
    """Return the membership of user id ``pk`` in ``workspace`` or None."""
    if not str(pk).isdigit():
        return None
    return UserWorkspace.objects.select_related('user').filter(workspace=workspace, user_id=pk).first()


class WorkspaceMemberViewSet(WorkspaceAdminMixin, viewsets.ViewSet):
    """List members of a workspace; owners may change roles and remove members."""

    def list(self, request, workspace_pk=None):
        workspace = self._get_workspace(workspace_pk)
        members = UserWorkspace.objects.filter(workspace=workspace).select_related('user')
        return Response(MemberSerializer(members, many=True).data)

    def partial_update(self, request, workspace_pk=None, pk=None):
        workspace = self._get_workspace(workspace_pk)
        self._require_owner(workspace, request.user, 'Only workspace owners can manage members.')

        membership = _member_lookup(workspace, pk)
        if membership is None:
            return Response({'detail': 'Member not found.'}, status=status.HTTP_404_NOT_FOUND)

        new_role = request.data.get('role')
        if new_role not in dict(UserWorkspace.ROLE_CHOICES):
            return Response({'detail': f'Invalid role: {new_role}'}, status=status.HTTP_400_BAD_REQUEST)
        if membership.user == request.user and new_role != UserWorkspace.ROLE_OWNER:
            return Response({'detail': 'You cannot demote yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        membership.role = new_role
        membership.save(update_fields=['role'])
        log_event(actor=request.user, workspace=workspace, action='MEMBER_ROLE_CHANGED',
                  target_user=membership.user, metadata={'new_role': new_role},
                  ip_address=get_client_ip(request))
        return Response(MemberSerializer(membership).data)

    def destroy(self, request, workspace_pk=None, pk=None):
        workspace = self._get_workspace(workspace_pk)
        self._require_owner(workspace, request.user, 'Only workspace owners can manage members.')

        if str(request.user.pk) == str(pk):
            return Response(
                {'detail': 'You cannot remove yourself from the workspace.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        membership = _member_lookup(workspace, pk)
        if membership is None:
            return Response({'detail': 'Member not found.'}, status=status.HTTP_404_NOT_FOUND)

        owner_count = UserWorkspace.objects.filter(workspace=workspace, role=UserWorkspace.ROLE_OWNER).count()
        if membership.role == UserWorkspace.ROLE_OWNER and owner_count <= 1:
            return Response(
                {'detail': 'Cannot remove the last owner of a workspace.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        removed = membership.user
        membership.delete()
        log_event(actor=request.user, workspace=workspace, action='MEMBER_REMOVED',
                  target_user=removed, metadata={'removed_user_id': removed.pk},
                  ip_address=get_client_ip(request))
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkspaceInviteViewSet(WorkspaceAdminMixin, viewsets.ViewSet):
    """List, create and revoke pending invites. Owner access only."""

    def _owner_workspace(self, request, workspace_pk):
        workspace = self._get_workspace(workspace_pk)
        self._require_owner(workspace, request.user, 'Only workspace owners can manage invites.')
        return workspace

    def list(self, request, workspace_pk=None):
        workspace = self._owner_workspace(request, workspace_pk)
        invites = WorkspaceInvite.objects.filter(
            workspace=workspace, status=WorkspaceInvite.STATUS_PENDING,
        ).select_related('invited_by')
        return Response(WorkspaceInviteSerializer(invites, many=True).data)

    def create(self, request, workspace_pk=None):
        workspace = self._owner_workspace(request, workspace_pk)
        serializer = WorkspaceInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            invite = create_invite(
                workspace=workspace,
                invited_by=request.user,
                email=serializer.validated_data['email'],
                role=serializer.validated_data.get('role', UserWorkspace.ROLE_MEMBER),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        log_event(actor=request.user, workspace=workspace, action='MEMBER_INVITED',
                  metadata={'email': invite.email, 'role': invite.role}, ip_address=get_client_ip(request))
        return Response(WorkspaceInviteSerializer(invite).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, workspace_pk=None, pk=None):
        workspace = self._owner_workspace(request, workspace_pk)
        deleted, _ = WorkspaceInvite.objects.filter(
            id=pk if str(pk).isdigit() else None, workspace=workspace, status=WorkspaceInvite.STATUS_PENDING,
        ).delete()
        if not deleted:
            return Response({'detail': 'Invite not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AcceptInviteView(APIView):
    """Accept an invite as the authenticated user."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, token):
        try:
            membership = accept_invite(token=token, user=request.user)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'workspace_id': membership.workspace_id,
            'workspace_slug': membership.workspace.slug,
            'role': membership.role,
        })


class WorkspaceAuditViewSet(WorkspaceAdminMixin, viewsets.ReadOnlyModelViewSet):
    """Read-only audit log, owner access only; filter with ``?action=``."""

    serializer_class = AuditEventSerializer

    def get_queryset(self):
        workspace = self._get_workspace(self.kwargs['workspace_pk'])
        self._require_owner(workspace, self.request.user, 'Audit log is visible to workspace owners only.')
        queryset = AuditEvent.objects.filter(workspace=workspace).select_related('actor', 'target_user', 'stream')
        action_filter = self.request.query_params.get('action')
        if action_filter:
            queryset = queryset.filter(action=action_filter)
        return queryset
