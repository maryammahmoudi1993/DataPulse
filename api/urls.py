from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter

from api.views import DataPointViewSet, StreamViewSet, WorkspaceViewSet

router = DefaultRouter()
router.register('workspaces', WorkspaceViewSet, basename='workspace')
router.register('streams', StreamViewSet, basename='stream')

streams_router = NestedDefaultRouter(router, 'streams', lookup='stream')
streams_router.register('datapoints', DataPointViewSet, basename='stream-datapoints')

urlpatterns = router.urls + streams_router.urls
