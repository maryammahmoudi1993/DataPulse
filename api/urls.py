from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter

from api.views import (
    AcceptInviteView,
    AlertViewSet,
    DataPointViewSet,
    StreamViewSet,
    WebhookEndpointViewSet,
    WorkspaceAuditViewSet,
    WorkspaceInviteViewSet,
    WorkspaceMemberViewSet,
    WorkspaceViewSet,
)

router = DefaultRouter()
router.register('workspaces', WorkspaceViewSet, basename='workspace')
router.register('streams', StreamViewSet, basename='stream')
router.register('webhooks', WebhookEndpointViewSet, basename='webhook')

streams_router = NestedDefaultRouter(router, 'streams', lookup='stream')
streams_router.register('datapoints', DataPointViewSet, basename='stream-datapoints')
streams_router.register('alerts', AlertViewSet, basename='stream-alerts')

workspaces_router = NestedDefaultRouter(router, 'workspaces', lookup='workspace')
workspaces_router.register('members', WorkspaceMemberViewSet, basename='workspace-members')
workspaces_router.register('invites', WorkspaceInviteViewSet, basename='workspace-invites')
workspaces_router.register('audit', WorkspaceAuditViewSet, basename='workspace-audit')

urlpatterns = router.urls + streams_router.urls + workspaces_router.urls + [
    path('invites/<str:token>/accept/', AcceptInviteView.as_view(), name='invite-accept'),
]
