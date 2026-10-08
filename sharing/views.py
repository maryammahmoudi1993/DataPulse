import logging

from django.db.models import F
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from alerts.models import Alert
from ingestion.models import DataPoint

from .models import DashboardShare

logger = logging.getLogger(__name__)

MAX_OPEN_ALERTS = 10

SHARE_RESPONSE = inline_serializer('PublicShare', {
    'title': serializers.CharField(),
    'stream_name': serializers.CharField(),
    'detector_type': serializers.CharField(),
    'expires_at': serializers.DateTimeField(),
    'view_count': serializers.IntegerField(),
    'points': serializers.ListField(child=serializers.DictField()),
    'open_alerts': serializers.ListField(child=serializers.DictField()),
})


class PublicShareView(APIView):
    """Public, unauthenticated read-only view of a shared stream.

    Subject to the anonymous throttle. Returns the last N data points, open
    alerts and basic stream metadata.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=['sharing'], summary='View a shared stream', responses={200: SHARE_RESPONSE})
    def get(self, request, token):
        try:
            share = DashboardShare.objects.select_related('stream').get(token=token, is_active=True)
        except DashboardShare.DoesNotExist:
            return Response({'detail': 'Share link not found or revoked.'}, status=404)

        if share.is_expired:
            return Response({'detail': 'This share link has expired.'}, status=410)

        DashboardShare.objects.filter(pk=share.pk).update(view_count=F('view_count') + 1)

        stream = share.stream
        points = list(
            DataPoint.objects.filter(stream=stream).order_by('-timestamp').values('timestamp', 'value')[:share.max_points]
        )
        points.reverse()
        alerts = (
            Alert.objects.filter(stream=stream, status=Alert.STATUS_OPEN)
            .order_by('-created_at')
            .values('severity', 'anomaly_score', 'timestamp', 'detector_type')[:MAX_OPEN_ALERTS]
        )

        logger.info('Share link viewed', extra={'token': token[:8], 'stream_id': stream.id})

        return Response({
            'title': share.title,
            'stream_name': stream.name,
            'detector_type': stream.detector_type,
            'expires_at': share.expires_at.isoformat(),
            'view_count': share.view_count + 1,
            'points': [{'timestamp': p['timestamp'].isoformat(), 'value': p['value']} for p in points],
            'open_alerts': [
                {
                    'severity': a['severity'],
                    'score': round(a['anomaly_score'], 3),
                    'timestamp': a['timestamp'].isoformat(),
                    'detector_type': a['detector_type'],
                }
                for a in alerts
            ],
        })
