from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter

from api.views import (
    AlertRuleViewSet,
    AcceptInviteView,
    AlertViewSet,
    APIKeyViewSet,
    DataPointIngestView,
    DataPointViewSet,
    NotificationLogViewSet,
    PagerDutyIntegrationViewSet,
    RetrieveInviteView,
    ShareViewSet,
    SlackIntegrationViewSet,
    StreamAnnotationViewSet,
    StreamViewSet,
    WebhookEndpointViewSet,
    WorkspaceAuditViewSet,
    WorkspaceInviteViewSet,
    WorkspaceMemberViewSet,
    WorkspaceViewSet,
)
from sharing.views import PublicShareView

router = DefaultRouter()
router.register('workspaces', WorkspaceViewSet, basename='workspace')
router.register('streams', StreamViewSet, basename='stream')
router.register('api-keys', APIKeyViewSet, basename='api-key')
router.register('shares', ShareViewSet, basename='share')
router.register('webhooks', WebhookEndpointViewSet, basename='webhook')
router.register('integrations/slack', SlackIntegrationViewSet, basename='slack-integration')
router.register('integrations/pagerduty', PagerDutyIntegrationViewSet, basename='pagerduty-integration')
router.register('integrations/notifications', NotificationLogViewSet, basename='notification-log')

streams_router = NestedDefaultRouter(router, 'streams', lookup='stream')
streams_router.register('datapoints', DataPointViewSet, basename='stream-datapoints')
streams_router.register('alerts', AlertViewSet, basename='stream-alerts')
streams_router.register('rules', AlertRuleViewSet, basename='stream-rules')
streams_router.register('annotations', StreamAnnotationViewSet, basename='stream-annotations')

workspaces_router = NestedDefaultRouter(router, 'workspaces', lookup='workspace')
workspaces_router.register('members', WorkspaceMemberViewSet, basename='workspace-members')
workspaces_router.register('invites', WorkspaceInviteViewSet, basename='workspace-invites')
workspaces_router.register('audit', WorkspaceAuditViewSet, basename='workspace-audit')

urlpatterns = router.urls + streams_router.urls + workspaces_router.urls + [
    path('streams/<int:stream_pk>/ingest/', DataPointIngestView.as_view(), name='datapoint-ingest'),
    path('share/<str:token>/', PublicShareView.as_view(), name='public-share'),
    path('invites/<str:token>/', RetrieveInviteView.as_view(), name='invite-detail'),
    path('invites/<str:token>/accept/', AcceptInviteView.as_view(), name='invite-accept'),
]
