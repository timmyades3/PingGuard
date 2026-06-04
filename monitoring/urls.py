from django.urls import include, path
from .views import *
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'ip-addresses', IPAddressViewset, basename='ip-address')
router.register(r'endpoints', EndpointViewset, basename='endpoint')
router.register(r'settings', SettingsViewset, basename='settings')
urlpatterns = [
    path('', include(router.urls)),
    path("group-all/", GroupEnpointIpAddressAPIView.as_view(), name = "group_all"),
    path("search/", SearchAPIView.as_view(), name="search"),
    path("start-monitoring/<int:ip_id>/", StartIPMonitoringAPIView.as_view(), name="start-monitoring"),
    path("stop-monitoring/<int:ip_id>/", StopIPMonitoringAPIView.as_view(), name="stop-monitoring"),
    path("start-endpoint-monitoring/<int:endpoint_id>/", StartEndpointMonitoringAPIView.as_view(), name="start-endpoint-monitoring"),
    path("stop-endpoint-monitoring/<int:endpoint_id>/", StopEndpointMonitoringAPIView.as_view(), name="stop-endpoint-monitoring"),
    path("group-start-monitoring-all/<int:group_id>/", StartAllGroupMonitoringAPIView.as_view(), name="group-all-monitoring"),
    path("group-stop-monitoring-all/<int:group_id>/", StopAllGroupMonitoringAPIView.as_view(), name="group-all-stop-monitoring"),
    path("dashboard/", DashboardAPIView.as_view(), name="dashboard"),
    path("stats/<int:id>/", StatsAPIView.as_view(), name="stats"),
]