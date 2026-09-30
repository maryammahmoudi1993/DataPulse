from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from alerts.models import Alert, WebhookEndpoint
from streams.models import Stream, Workspace

from api.serializers import (
    AlertSerializer,
    DataPointSerializer,
    StreamSerializer,
    WebhookEndpointSerializer,
    WorkspaceSerializer,
)
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


class StreamViewSet(viewsets.ModelViewSet):
    serializer_class = StreamSerializer
    permission_classes = [IsAuthenticatedOrPublicDemo]

    def get_queryset(self):
        return Stream.objects.filter(workspace__in=Workspace.accessible_to(self.request.user))

    def perform_create(self, serializer):
        workspace = serializer.validated_data.get('workspace')
        get_object_or_404(Workspace.accessible_to(self.request.user), pk=workspace.pk)
        serializer.save()

    @action(detail=True, methods=['post'])
    def pause(self, request, *args, **kwargs):
        stream = self.get_object()
        stream.status = Stream.STATUS_PAUSED
        stream.save(update_fields=['status'])
        return Response(StreamSerializer(stream).data)

    @action(detail=True, methods=['post'])
    def resume(self, request, *args, **kwargs):
        stream = self.get_object()
        stream.status = Stream.STATUS_ACTIVE
        stream.save(update_fields=['status'])
        return Response(StreamSerializer(stream).data)


class DataPointViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = DataPointSerializer

    def get_queryset(self):
        stream_pk = self.kwargs.get('stream_pk')
        return DataPoint.objects.filter(
            stream_id=stream_pk,
            stream__workspace__in=Workspace.accessible_to(self.request.user),
        )


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
        return Response(AlertSerializer(alert).data)


class WebhookEndpointViewSet(viewsets.ModelViewSet):
    serializer_class = WebhookEndpointSerializer

    def get_queryset(self):
        return WebhookEndpoint.objects.filter(workspace__in=Workspace.accessible_to(self.request.user))

    def perform_create(self, serializer):
        workspace = serializer.validated_data.get('workspace')
        get_object_or_404(Workspace.accessible_to(self.request.user), pk=workspace.pk)
        serializer.save()
