from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from streams.models import Stream

from api.serializers import DataPointSerializer, StreamSerializer, WorkspaceSerializer
from ingestion.models import DataPoint


class WorkspaceViewSet(viewsets.ModelViewSet):
    serializer_class = WorkspaceSerializer

    def get_queryset(self):
        return self.request.user.workspace_set.all()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class StreamViewSet(viewsets.ModelViewSet):
    serializer_class = StreamSerializer

    def get_queryset(self):
        return Stream.objects.filter(workspace__in=self.request.user.workspace_set.all())

    def perform_create(self, serializer):
        workspace = serializer.validated_data.get('workspace')
        get_object_or_404(self.request.user.workspace_set, pk=workspace.pk)
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
            stream__workspace__in=self.request.user.workspace_set.all(),
        )
