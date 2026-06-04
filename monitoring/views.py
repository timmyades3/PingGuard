# pyrefly: ignore [missing-import]
from datetime import timedelta
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.shortcuts import render
from django.db.models import Q, OuterRef, Subquery, Count, Avg, Sum, F, FloatField
from rest_framework import request, viewsets, permissions, status, mixins
from .permissions import IsOwner
from .models import Group, IpAddress, Endpoint, MonitorCheck, HourlyStat, DailyStat, Settings
from .serializers import (
    GroupSerializer,
    IpAddressSerializer,
    EndpointSerializer,
    MonitorCheckSerializer,
    HourlyStatSerializer,
    DailyStatSerializer,
    SettingsSerializer,
)
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from utils.pagination import StandardResultsSetPagination
from .tasks import check_endpoint, ping_ip


# Create your views here.
@method_decorator(name="list", decorator=swagger_auto_schema(tags=["Groups"]))
@method_decorator(name="create", decorator=swagger_auto_schema(tags=["Groups"]))
@method_decorator(name="retrieve", decorator=swagger_auto_schema(tags=["Groups"]))
@method_decorator(name="update", decorator=swagger_auto_schema(tags=["Groups"]))
@method_decorator(name="partial_update", decorator=swagger_auto_schema(tags=["Groups"]))
@method_decorator(name="destroy", decorator=swagger_auto_schema(tags=["Groups"]))
class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    queryset = Group.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Group.objects.none()
        return Group.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@method_decorator(name="list", decorator=swagger_auto_schema(tags=["IP Addresses"]))
@method_decorator(name="create", decorator=swagger_auto_schema(tags=["IP Addresses"]))
@method_decorator(name="retrieve", decorator=swagger_auto_schema(tags=["IP Addresses"]))
@method_decorator(name="update", decorator=swagger_auto_schema(tags=["IP Addresses"]))
@method_decorator(
    name="partial_update", decorator=swagger_auto_schema(tags=["IP Addresses"])
)
@method_decorator(name="destroy", decorator=swagger_auto_schema(tags=["IP Addresses"]))
class IPAddressViewset(viewsets.ModelViewSet):
    serializer_class = IpAddressSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    queryset = IpAddress.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return IpAddress.objects.none()
        return IpAddress.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@method_decorator(name="list", decorator=swagger_auto_schema(tags=["Endpoints"]))
@method_decorator(name="create", decorator=swagger_auto_schema(tags=["Endpoints"]))
@method_decorator(name="retrieve", decorator=swagger_auto_schema(tags=["Endpoints"]))
@method_decorator(name="update", decorator=swagger_auto_schema(tags=["Endpoints"]))
@method_decorator(
    name="partial_update", decorator=swagger_auto_schema(tags=["Endpoints"])
)
@method_decorator(name="destroy", decorator=swagger_auto_schema(tags=["Endpoints"]))
class EndpointViewset(viewsets.ModelViewSet):
    serializer_class = EndpointSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    queryset = Endpoint.objects.all()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Endpoint.objects.none()
        return Endpoint.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

@method_decorator(name="list", decorator=swagger_auto_schema(tags=["Settings"]))
@method_decorator(name="update", decorator=swagger_auto_schema(tags=["Settings"]))
@method_decorator(
    name="partial_update", decorator=swagger_auto_schema(tags=["Settings"])
)
class SettingsViewset(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = SettingsSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    queryset = Settings.objects.all()
    pagination_class = None  
    http_method_names = ["get", "put", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Settings.objects.none()
        return Settings.objects.filter(user=self.request.user)


class GroupEnpointIpAddressAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    group_id_param_config = openapi.Parameter(
        "group_id",
        in_=openapi.IN_QUERY,
        description="description",
        type=openapi.TYPE_INTEGER,
    )
    page_param_config = openapi.Parameter(
        "page",
        in_=openapi.IN_QUERY,
        description="description",
        type=openapi.TYPE_INTEGER,
    )

    @swagger_auto_schema(
        tags=["Groups"], manual_parameters=[group_id_param_config, page_param_config]
    )
    def get(
        self,
        request,
    ):
        try:
            group_id = request.GET.get("group_id")
            group = Group.objects.get(id=group_id, user=request.user)
        except Group.DoesNotExist:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )

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
    search_param_config = openapi.Parameter(
        "q", in_=openapi.IN_QUERY, description="Search term", type=openapi.TYPE_STRING
    )
    page_param_config = openapi.Parameter(
        "page",
        in_=openapi.IN_QUERY,
        description="description",
        type=openapi.TYPE_INTEGER,
    )

    @swagger_auto_schema(
        tags=["Search"], manual_parameters=[search_param_config, page_param_config]
    )
    def get(self, request):
        query = request.GET.get("q", "")

        if not query:
            return Response([], status=status.HTTP_200_OK)

        endpoints = Endpoint.objects.filter(
            Q(user=request.user) & (Q(label__icontains=query) | Q(url__icontains=query))
        )

        ip_addresses = IpAddress.objects.filter(
            Q(user=request.user)
            & (Q(label__icontains=query) | Q(ip_address__icontains=query))
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

    @swagger_auto_schema(tags=["IP Addresses"])
    def patch(self, request, ip_id=None):
        try:
            ip_address = IpAddress.objects.get(id=ip_id, user=request.user)
        except IpAddress.DoesNotExist:
            return Response(
                {"detail": "IP address not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not ip_address.is_active:
            ip_address.is_active = True
            ip_address.save()

            # Start the self-rescheduling task loop
            ping_ip.delay(ip_address.id)

            return Response(
                {"message": "Monitoring started for IP address."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "Monitoring is already active for this IP address."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class StopIPMonitoringAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    @swagger_auto_schema(tags=["IP Addresses"])
    def patch(self, request, ip_id=None):
        try:
            ip_address = IpAddress.objects.get(id=ip_id, user=request.user)
        except IpAddress.DoesNotExist:
            return Response(
                {"detail": "IP address not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if ip_address.is_active:
            ip_address.is_active = False
            ip_address.save()

            # The background task checks is_active. Since we set it to False, it will stop itself.
            return Response(
                {"message": "Monitoring stopped for IP address."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "Monitoring is already stopped."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class StartEndpointMonitoringAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    @swagger_auto_schema(tags=["Endpoints"])
    def patch(self, request, endpoint_id=None):
        try:
            endpoint = Endpoint.objects.get(id=endpoint_id, user=request.user)
        except Endpoint.DoesNotExist:
            return Response(
                {"detail": "Endpoint not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if not endpoint.is_active:
            endpoint.is_active = True
            endpoint.save()

            # Start the self-rescheduling task loop
            check_endpoint.delay(endpoint.id)

            return Response(
                {"message": "Monitoring started for Endpoint."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "Monitoring is already active for this Endpoint."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class StopEndpointMonitoringAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    @swagger_auto_schema(tags=["Endpoints"])
    def patch(self, request, endpoint_id=None):
        try:
            endpoint = Endpoint.objects.get(id=endpoint_id, user=request.user)
        except Endpoint.DoesNotExist:
            return Response(
                {"detail": "Endpoint not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if endpoint.is_active:
            endpoint.is_active = False
            endpoint.save()

            # The background task checks is_active. Since we set it to False, it will stop itself.
            return Response(
                {"message": "Monitoring stopped for Endpoint."},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "Monitoring is already stopped."},
            status=status.HTTP_400_BAD_REQUEST,
        )


# an endpoint to start and stop monitoring all endpoint and ip in a group
class StartAllGroupMonitoringAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    @swagger_auto_schema(tags=["Groups"])
    def patch(self, request, group_id=None):
        try:
            group = Group.objects.get(id=group_id, user=request.user)
        except Group.DoesNotExist:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )

        # check if any endpoint or ip in the group is already active. If yes, skip them and not add them to list of endpoint and ip to start monitoring.
        endpoints_to_start = Endpoint.objects.filter(group=group, is_active=False)
        ips_to_start = IpAddress.objects.filter(group=group, is_active=False)
        if endpoints_to_start.exists() or ips_to_start.exists():
            endpoints_to_start.update(is_active=True)
            ips_to_start.update(is_active=True)

            # Start the self-rescheduling task loop for each endpoint and ip in the group that is not active. The task will check if the endpoint or ip is active before performing the check, so we can safely call the task for all endpoints and ips in the group without worrying about duplicates or already active ones.
            for endpoint in endpoints_to_start:
                check_endpoint.delay(endpoint.id)
            for ip in ips_to_start:
                ping_ip.delay(ip.id)

            return Response(
                {"message": "Monitoring started for Group."}, status=status.HTTP_200_OK
            )

        return Response(
            {"message": "Monitoring is already active for this Group."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class StopAllGroupMonitoringAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    @swagger_auto_schema(tags=["Groups"])
    def patch(self, request, group_id=None):
        try:
            group = Group.objects.get(id=group_id, user=request.user)
        except Group.DoesNotExist:
            return Response(
                {"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND
            )

        endpoints_to_stop = Endpoint.objects.filter(group=group, is_active=True)
        ips_to_stop = IpAddress.objects.filter(group=group, is_active=True)
        if endpoints_to_stop.exists() or ips_to_stop.exists():
            endpoints_to_stop.update(is_active=False)
            ips_to_stop.update(is_active=False)

            return Response(
                {"message": "Monitoring stopped for Group."}, status=status.HTTP_200_OK
            )

        return Response(
            {"message": "Monitoring is already stopped for this Group."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class DashboardAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    @swagger_auto_schema(tags=["Stats"])
    def get(self, request):
        total_endpoints = Endpoint.objects.filter(user=request.user).count()
        total_ip_addresses = IpAddress.objects.filter(user=request.user).count()
        active_endpoints = Endpoint.objects.filter(
            user=request.user, is_active=True
        ).count()
        active_ip_addresses = IpAddress.objects.filter(
            user=request.user, is_active=True
        ).count()
        # Count unique targets (endpoints + IPs) whose latest check status is UP/DOWN
        latest_endpoint_status = (
            MonitorCheck.objects.filter(endpoint=OuterRef("pk"))
            .order_by("-checked_at")
            .values("status")[:1]
        )
        endpoint_qs = Endpoint.objects.filter(user=request.user).annotate(
            latest_status=Subquery(latest_endpoint_status)
        )
        endpoint_up = endpoint_qs.filter(latest_status="UP").count()
        endpoint_down = endpoint_qs.filter(latest_status="DOWN").count()

        latest_ip_status = (
            MonitorCheck.objects.filter(ip_address=OuterRef("pk"))
            .order_by("-checked_at")
            .values("status")[:1]
        )
        ip_qs = IpAddress.objects.filter(user=request.user).annotate(
            latest_status=Subquery(latest_ip_status)
        )
        ip_up = ip_qs.filter(latest_status="UP").count()
        ip_down = ip_qs.filter(latest_status="DOWN").count()

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


class StatsAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)

    stat_type_param_config = openapi.Parameter(
        "stat_type",
        in_=openapi.IN_QUERY,
        description="Type of stats: hourly, daily, five_minute, all_time",
        type=openapi.TYPE_STRING,
    )
    target_type_param_config = openapi.Parameter(
        "target_type",
        in_=openapi.IN_QUERY,
        description="Target type: ENDPOINT or IP",
        type=openapi.TYPE_STRING,
    )

    @swagger_auto_schema(
        tags=["Stats"],
        manual_parameters=[stat_type_param_config, target_type_param_config],
    )
    def get(self, request, id=None):
        stat_type = request.GET.get("stat_type")
        target_type = request.GET.get("target_type")

        if id is not None:
            try:
                if target_type == "ENDPOINT":
                    Endpoint.objects.get(id=id, user=request.user)
                else:
                    IpAddress.objects.get(id=id, user=request.user)
            except (Endpoint.DoesNotExist, IpAddress.DoesNotExist):
                return Response(
                    {f"detail": f"Invalid {target_type.lower()} id."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if not stat_type:
            return Response(
                {"detail": "stat_type query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if stat_type not in ["hourly", "daily", "five_minute", "all_time"]:
            return Response(
                {
                    "detail": "Invalid stat_type. Must be one of: hourly, daily, five_minute, all_time."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not target_type:
            return Response(
                {"detail": "target_type query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if target_type not in ["ENDPOINT", "IP"]:
            return Response(
                {"detail": "Invalid target_type. Must be one of: ENDPOINT, IP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if stat_type == "hourly":
            hourly_stats = HourlyStat.objects.filter(
                user=request.user,
                target_type=target_type,
                ip_address=id if target_type == "IP" else None,
                endpoint=id if target_type == "ENDPOINT" else None,
            ).order_by("-hour")
            data = HourlyStatSerializer(hourly_stats, many=True).data
            return Response(data, status=status.HTTP_200_OK)

        if stat_type == "daily":
            daily_stats = DailyStat.objects.filter(
                user=request.user,
                target_type=target_type,
                ip_address=id if target_type == "IP" else None,
                endpoint=id if target_type == "ENDPOINT" else None,
            ).order_by("-day")
            data = DailyStatSerializer(daily_stats, many=True).data
            return Response(data, status=status.HTTP_200_OK)

        if stat_type == "five_minute":
            # five_minute_stats = MonitorCheck.objects.filter(user=request.user, target_type=target_type).order_by('-checked_at')[:100]
            five_minute_stats = MonitorCheck.objects.filter(
                user=request.user,
                target_type=target_type,
                ip_address=id if target_type == "IP" else None,
                endpoint=id if target_type == "ENDPOINT" else None,
            ).order_by("-checked_at")
            data = MonitorCheckSerializer(five_minute_stats, many=True).data
            return Response(data, status=status.HTTP_200_OK)

        if stat_type == "all_time":
            hourly_stats = HourlyStat.objects.filter(
                user=request.user,
                target_type=target_type,
                ip_address=id if target_type == "IP" else None,
                endpoint=id if target_type == "ENDPOINT" else None,
            ).order_by("-hour")

            daily_stats = DailyStat.objects.filter(
                user=request.user,
                target_type=target_type,
                ip_address=id if target_type == "IP" else None,
                endpoint=id if target_type == "ENDPOINT" else None,
            ).order_by("-day")

            five_minute_qs = MonitorCheck.objects.filter(
                user=request.user,
                target_type=target_type,
                ip_address=id if target_type == "IP" else None,
                endpoint=id if target_type == "ENDPOINT" else None,
            ).order_by("-checked_at")

            # Aggregates for raw checks (five_minute)
            five_minute_agg = five_minute_qs.aggregate(
                total_checks=Count("id"),
                up_count=Count("id", filter=Q(status="UP")),
                down_count=Count("id", filter=Q(status="DOWN")),
                avg_response_time_ms=Avg("response_time_ms"),
            )

            # Aggregates for hourly_stats (sum of counts, weighted avg response)
            hourly_agg = hourly_stats.aggregate(
                sum_total_checks=Sum("total_checks"),
                sum_up_count=Sum("up_count"),
                sum_down_count=Sum("down_count"),
                weighted_resp_sum=Sum(
                    F("avg_response_time_ms") * F("total_checks"),
                    output_field=FloatField(),
                ),
            )
            hourly_total_checks = hourly_agg.get("sum_total_checks") or 0
            hourly_avg_resp = (
                (hourly_agg.get("weighted_resp_sum") / hourly_total_checks)
                if hourly_total_checks
                else None
            )

            # Aggregates for daily_stats
            daily_agg = daily_stats.aggregate(
                sum_total_checks=Sum("total_checks"),
                sum_up_count=Sum("up_count"),
                sum_down_count=Sum("down_count"),
                weighted_resp_sum=Sum(
                    F("avg_response_time_ms") * F("total_checks"),
                    output_field=FloatField(),
                ),
            )
            daily_total_checks = daily_agg.get("sum_total_checks") or 0
            daily_avg_resp = (
                (daily_agg.get("weighted_resp_sum") / daily_total_checks)
                if daily_total_checks
                else None
            )

            # Prepare five_minute values safely
            fm_total = five_minute_agg.get("total_checks") or 0
            fm_up = five_minute_agg.get("up_count") or 0
            fm_down = five_minute_agg.get("down_count") or 0
            fm_avg_resp = five_minute_agg.get("avg_response_time_ms")

            # Combined totals (sum counts across sources). Note: this may double-count checks
            combined_total_checks = (
                fm_total + (hourly_total_checks or 0) + (daily_total_checks or 0)
            )
            combined_up = (
                fm_up
                + (hourly_agg.get("sum_up_count") or 0)
                + (daily_agg.get("sum_up_count") or 0)
            )
            combined_down = (
                fm_down
                + (hourly_agg.get("sum_down_count") or 0)
                + (daily_agg.get("sum_down_count") or 0)
            )

            # Combined weighted average response calculation across sources
            combined_weighted_resp = 0.0
            combined_weighted_resp += (fm_avg_resp or 0.0) * fm_total
            combined_weighted_resp += (hourly_avg_resp or 0.0) * (
                hourly_total_checks or 0
            )
            combined_weighted_resp += (daily_avg_resp or 0.0) * (
                daily_total_checks or 0
            )
            combined_avg_resp = (
                (combined_weighted_resp / combined_total_checks)
                if combined_total_checks
                else None
            )

            combined_uptime_percent = (
                (combined_up / combined_total_checks * 100.0)
                if combined_total_checks
                else None
            )

            data = {
                "daily_stats": DailyStatSerializer(daily_stats, many=True).data,
                "hourly_stats": HourlyStatSerializer(hourly_stats, many=True).data,
                "five_minute_stats": MonitorCheckSerializer(
                    five_minute_qs, many=True
                ).data,
                "aggregates": {
                    "five_minute": {
                        "total_checks": fm_total,
                        "up_count": fm_up,
                        "down_count": fm_down,
                        "avg_response_time_ms": fm_avg_resp,
                        "uptime_percent": (
                            (fm_up / fm_total * 100.0) if fm_total else None
                        ),
                    },
                    "hourly": {
                        "total_checks": hourly_total_checks,
                        "up_count": hourly_agg.get("sum_up_count") or 0,
                        "down_count": hourly_agg.get("sum_down_count") or 0,
                        "avg_response_time_ms": hourly_avg_resp,
                        "uptime_percent": (
                            (
                                (hourly_agg.get("sum_up_count") or 0)
                                / hourly_total_checks
                                * 100.0
                            )
                            if hourly_total_checks
                            else None
                        ),
                    },
                    "daily": {
                        "total_checks": daily_total_checks,
                        "up_count": daily_agg.get("sum_up_count") or 0,
                        "down_count": daily_agg.get("sum_down_count") or 0,
                        "avg_response_time_ms": daily_avg_resp,
                        "uptime_percent": (
                            (
                                (daily_agg.get("sum_up_count") or 0)
                                / daily_total_checks
                                * 100.0
                            )
                            if daily_total_checks
                            else None
                        ),
                    },
                    "combined": {
                        "total_checks": combined_total_checks,
                        "up_count": combined_up,
                        "down_count": combined_down,
                        "avg_response_time_ms": combined_avg_resp,
                        "uptime_percent": combined_uptime_percent,
                    },
                },
            }
            return Response(data, status=status.HTTP_200_OK)


