from django.urls import include, path
from .views import GroupViewSet, IPAddressViewset, EndpointViewset, GroupEnpointIpAddressAPIView
from rest_framework.routers import DefaultRouter


router = DefaultRouter()
router.register(r'groups', GroupViewSet, basename='group')
router.register(r'ip-addresses', IPAddressViewset, basename='ip-address')
router.register(r'endpoints', EndpointViewset, basename='endpoint')

urlpatterns = [
    path('', include(router.urls)),
    path("group_all/", GroupEnpointIpAddressAPIView.as_view(), name = "group_all"),
]