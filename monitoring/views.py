# pyrefly: ignore [missing-import]
from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render
from django.db.models import Q, OuterRef, Subquery
from rest_framework import request, viewsets,permissions, status
from .permissions import IsOwner
from .models import Group, IpAddress, Endpoint, MonitorCheck, HourlyStat, DailyStat
from .serializers import GroupSerializer, IpAddressSerializer, EndpointSerializer, MonitorCheckSerializer, HourlyStatSerializer, DailyStatSerializer
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

            return Response({"message": "Monitoring started for Endpoint."}, status=status.HTTP_200_OK)    

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


class DashboardAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    def get(self, request):
        total_endpoints = Endpoint.objects.filter(user=request.user).count()
        total_ip_addresses = IpAddress.objects.filter(user=request.user).count()
        active_endpoints = Endpoint.objects.filter(user=request.user, is_active=True).count()
        active_ip_addresses = IpAddress.objects.filter(user=request.user, is_active=True).count()
        # Count unique targets (endpoints + IPs) whose latest check status is UP/DOWN
        latest_endpoint_status = MonitorCheck.objects.filter(endpoint=OuterRef('pk')).order_by('-checked_at').values('status')[:1]
        endpoint_qs = Endpoint.objects.filter(user=request.user).annotate(latest_status=Subquery(latest_endpoint_status))
        endpoint_up = endpoint_qs.filter(latest_status='UP').count()
        endpoint_down = endpoint_qs.filter(latest_status='DOWN').count()

        latest_ip_status = MonitorCheck.objects.filter(ip_address=OuterRef('pk')).order_by('-checked_at').values('status')[:1]
        ip_qs = IpAddress.objects.filter(user=request.user).annotate(latest_status=Subquery(latest_ip_status))
        ip_up = ip_qs.filter(latest_status='UP').count()
        ip_down = ip_qs.filter(latest_status='DOWN').count()

        total_up_count = endpoint_up + ip_up
        total_down_count = endpoint_down + ip_down

        data = {
            "total_endpoints": total_endpoints,
            "total_ip_addresses": total_ip_addresses,
            "active_endpoints": active_endpoints,
            "active_ip_addresses": active_ip_addresses,
            "total_up_count": total_up_count,
            "total_down_count": total_down_count,
        }
        return Response(data, status=status.HTTP_200_OK)
    

#get stats for hourly and daily stats five minutes stats and all time stats agregate where user use query param and url query param to specify if they want endpoint or ip stats and also specify if they want hourly, daily stats, five minute stats or all time stats 
class StatsAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    stat_type_param_config = openapi.Parameter('stat_type', in_=openapi.IN_QUERY, description='Type of stats: hourly, daily, five_minute, all_time', type=openapi.TYPE_STRING)
    target_type_param_config = openapi.Parameter('target_type', in_=openapi.IN_QUERY, description='Target type: endpoint or ip', type=openapi.TYPE_STRING)

    @swagger_auto_schema(manual_parameters=[stat_type_param_config, target_type_param_config])
    def get(self, request, id = None):
        stat_type = request.GET.get('stat_type')
        target_type = request.GET.get('target_type')

        if stat_type not in ['hourly', 'daily', 'five_minute', 'all_time']:
            return Response({"detail": "Invalid stat_type. Must be one of: hourly, daily, five_minute, all_time."}, status=status.HTTP_400_BAD_REQUEST)
        
        if target_type not in ['endpoint', 'ip']:
            return Response({"detail": "Invalid target_type. Must be one of: endpoint, ip."}, status=status.HTTP_400_BAD_REQUEST)
        
        if stat_type == 'hourly':
            hourly_stats = HourlyStat.objects.filter(user=request.user,target_type=target_type,ip_address=id if target_type == 'ip' else None, endpoint=id if target_type == 'endpoint' else None).order_by('-hour')
            print(hourly_stats)
            data = HourlyStatSerializer(hourly_stats, many=True).data
            print(data)
            return Response(data, status=status.HTTP_200_OK)
            
        if stat_type == 'daily':
            daily_stats = DailyStat.objects.filter(user=request.user,target_type=target_type,ip_address=id if target_type == 'ip' else None, endpoint=id if target_type == 'endpoint' else None).order_by('-day')
            data = DailyStatSerializer(daily_stats, many=True).data
            return Response(data, status=status.HTTP_200_OK)
            
        if stat_type == 'five_minute': 
            five_minute_stats = MonitorCheck.objects.filter(user=request.user, target_type=target_type,ip_address=id if target_type == 'ip' else None, endpoint=id if target_type == 'endpoint' else None).order_by('-checked_at')[:100]
            # five_minute_stats = MonitorCheck.objects.filter(user=request.user, target_type=target_type,ip_address=id if target_type == 'ip' else None, endpoint=id if target_type == 'endpoint' else None).order_by('-checked_at')
            data = MonitorCheckSerializer(five_minute_stats, many=True).data
            return Response(data, status=status.HTTP_200_OK)
            
        if stat_type == 'all_time':
            hourly_stats = HourlyStat.objects.filter(user=request.user,target_type=target_type,ip_address=id if target_type == 'ip' else None, endpoint=id if target_type == 'endpoint' else None).order_by('-hour')
            daily_stats = DailyStat.objects.filter(user=request.user,target_type=target_type,ip_address=id if target_type == 'ip' else None, endpoint=id if target_type == 'endpoint' else None).order_by('-day')
            five_minute_stats = MonitorCheck.objects.filter(user=request.user, target_type=target_type,ip_address=id if target_type == 'ip' else None, endpoint=id if target_type == 'endpoint' else None).order_by('-checked_at')
            
            data = {
                "daily_stats": DailyStatSerializer(daily_stats, many=True).data,
                "hourly_stats": HourlyStatSerializer(hourly_stats, many=True).data,
                "five_minute_stats": MonitorCheckSerializer(five_minute_stats, many=True).data
            }
            return Response(data, status=status.HTTP_200_OK)