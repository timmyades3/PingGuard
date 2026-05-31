# pyrefly: ignore [missing-import]
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render
from django.db.models import Q
from rest_framework import viewsets,permissions, status
from .permissions import IsOwner
from .models import Group, IpAddress, Endpoint
from .serializers import GroupSerializer, IpAddressSerializer, EndpointSerializer
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from utils.pagination import StandardResultsSetPagination
from .tasks import check_endpoint, ping_ip


# Create your views here.
class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = (permissions.IsAuthenticated,IsOwner)
    queryset = Group.objects.all()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Group.objects.none()
        return Group.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)



class IPAddressViewset(viewsets.ModelViewSet):
    serializer_class = IpAddressSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    queryset = IpAddress.objects.all()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return IpAddress.objects.none()
        return IpAddress.objects.filter(user = self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class EndpointViewset(viewsets.ModelViewSet):
    serializer_class = EndpointSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    queryset = Endpoint.objects.all()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Endpoint.objects.none()
        return Endpoint.objects.filter(user = self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class GroupEnpointIpAddressAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    group_id_param_config = openapi.Parameter('group_id',in_=openapi.IN_QUERY,description='description',type=openapi.TYPE_INTEGER)
    page_param_config = openapi.Parameter('page',in_=openapi.IN_QUERY,description='description',type=openapi.TYPE_INTEGER)
    @swagger_auto_schema(manual_parameters=[group_id_param_config, page_param_config])

    def get(self, request,):
        try:
            group_id = request.GET.get("group_id")
            group  =  Group.objects.get(id  = group_id, user = request.user)
        except Group.DoesNotExist:
            return Response({"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND)

        endpoint = Endpoint.objects.filter(group=group)
        ip_address = IpAddress.objects.filter(group=group)

        endpoint_data = EndpointSerializer(endpoint, many=True).data
        ip_address_data = IpAddressSerializer(ip_address, many=True).data

        for endpoint in endpoint_data:
            endpoint["type"] = "endpoint"
        for ip in ip_address_data:
            ip["type"] = "ip"

        data = endpoint_data + ip_address_data

        # Paginate the combined data
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(data, request)
        return paginator.get_paginated_response(page)
    
class SearchAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    search_param_config = openapi.Parameter('q', in_=openapi.IN_QUERY, description='Search term', type=openapi.TYPE_STRING)
    page_param_config = openapi.Parameter('page',in_=openapi.IN_QUERY,description='description',type=openapi.TYPE_INTEGER)

    @swagger_auto_schema(manual_parameters=[search_param_config, page_param_config])
    def get(self, request):
        query = request.GET.get('q', '')
        
        if not query:
            return Response([], status=status.HTTP_200_OK)
            
        endpoints = Endpoint.objects.filter(
            Q(user=request.user) & 
            (Q(label__icontains=query) | Q(url__icontains=query))
        )
        
        ip_addresses = IpAddress.objects.filter(
            Q(user=request.user) & 
            (Q(label__icontains=query) | Q(ip_address__icontains=query))
        )
        
        endpoint_data = EndpointSerializer(endpoints, many=True).data
        ip_address_data = IpAddressSerializer(ip_addresses, many=True).data
        
        for endpoint in endpoint_data:
            endpoint["type"] = "endpoint"
        for ip in ip_address_data:
            ip["type"] = "ip"
            
        data = endpoint_data + ip_address_data

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(data, request)
        return paginator.get_paginated_response(page)
    
class StartIPMonitoringAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    def patch(self, request, ip_id=None):
        try:
            ip_address = IpAddress.objects.get(id=ip_id, user=request.user)
        except IpAddress.DoesNotExist:
            return Response({"detail": "IP address not found."}, status=status.HTTP_404_NOT_FOUND)
            
        if not ip_address.is_active:
            ip_address.is_active = True
            ip_address.save()
            
            # Start the self-rescheduling task loop
            ping_ip.delay(ip_address.id)

            return Response({"message": "Monitoring started for IP address."}, status=status.HTTP_200_OK)    

        return Response({"message": "Monitoring is already active for this IP address."}, status=status.HTTP_400_BAD_REQUEST)

class StopIPMonitoringAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    def patch(self, request, ip_id=None):
        try:
            ip_address = IpAddress.objects.get(id=ip_id, user=request.user)
        except IpAddress.DoesNotExist:
            return Response({"detail": "IP address not found."}, status=status.HTTP_404_NOT_FOUND)

        if ip_address.is_active:
            ip_address.is_active = False
            ip_address.save()
            
            # The background task checks is_active. Since we set it to False, it will stop itself.
            return Response({"message": "Monitoring stopped for IP address."}, status=status.HTTP_200_OK)    

        return Response({"message": "Monitoring is already stopped."}, status=status.HTTP_400_BAD_REQUEST)


class StartEndpointMonitoringAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    def patch(self, request, endpoint_id=None):
        try:
            endpoint = Endpoint.objects.get(id=endpoint_id, user=request.user)
        except Endpoint.DoesNotExist:
            return Response({"detail": "Endpoint not found."}, status=status.HTTP_404_NOT_FOUND)
            
        if not endpoint.is_active:
            endpoint.is_active = True
            endpoint.save()
            
            # Start the self-rescheduling task loop
            check_endpoint.delay(endpoint.id)

            return Response({"message": "Monitoring started for Endpoint (every 5 mins)."}, status=status.HTTP_200_OK)    

        return Response({"message": "Monitoring is already active for this Endpoint."}, status=status.HTTP_400_BAD_REQUEST)

class StopEndpointMonitoringAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    def patch(self, request, endpoint_id=None):
        try:
            endpoint = Endpoint.objects.get(id=endpoint_id, user=request.user)
        except Endpoint.DoesNotExist:
            return Response({"detail": "Endpoint not found."}, status=status.HTTP_404_NOT_FOUND)

        if endpoint.is_active:
            endpoint.is_active = False
            endpoint.save()
            
            # The background task checks is_active. Since we set it to False, it will stop itself.
            return Response({"message": "Monitoring stopped for Endpoint."}, status=status.HTTP_200_OK)    

        return Response({"message": "Monitoring is already stopped."}, status=status.HTTP_400_BAD_REQUEST)


