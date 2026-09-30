from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter

from api.views import (
    AlertViewSet,
    DataPointViewSet,
    StreamViewSet,
    WebhookEndpointViewSet,
    WorkspaceViewSet,
)

router = DefaultRouter()
router.register('workspaces', WorkspaceViewSet, basename='workspace')
router.register('streams', StreamViewSet, basename='stream')
router.register('webhooks', WebhookEndpointViewSet, basename='webhook')

streams_router = NestedDefaultRouter(router, 'streams', lookup='stream')
streams_router.register('datapoints', DataPointViewSet, basename='stream-datapoints')
streams_router.register('alerts', AlertViewSet, basename='stream-alerts')

urlpatterns = router.urls + streams_router.urls
