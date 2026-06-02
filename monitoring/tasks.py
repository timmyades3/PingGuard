from datetime import timedelta
from django.utils import timezone
import re
import time
from celery import shared_task
import subprocess
import platform
from .models import IpAddress, Endpoint, MonitorCheck, HourlyStat, DailyStat
import requests
import logging
import socket
import ssl
from django.db import close_old_connections
from django.db.models import Avg, Count, Q, Sum, F, FloatField
from django.db.models.functions import TruncHour, TruncDay, TruncMinute
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task(name="monitoring.tasks.master_monitor_check")
def master_monitor_check():
    close_old_connections()

    active_ips = IpAddress.objects.filter(is_active=True)
    active_endpoints = Endpoint.objects.filter(is_active=True)

    if not active_ips.exists() and not active_endpoints.exists():
        msg = "Idle: No active IPs or Endpoints"
        logger.info(msg)
        return msg

    for ip in active_ips:
        ping_ip.delay(ip.id)

    for endpoint in active_endpoints:
        check_endpoint.delay(endpoint.id)

    msg = (
        f"Dispatched {active_ips.count()} IPs and {active_endpoints.count()} Endpoints"
    )
    logger.info(msg)
    return msg


@shared_task(name="monitoring.tasks.ping_ip")
def ping_ip(ip_id):
    close_old_connections()

    try:
        ip = IpAddress.objects.select_related("user").get(id=ip_id)
    except IpAddress.DoesNotExist:
        logger.warning("Ip not found")
        return "Ip not found"

    # Optional: If the IP is no longer active, we could skip monitoring
    if not ip.is_active:
        msg = f"Monitoring stopped for IP: {ip.ip_address}"
        logger.info(msg)
        return msg

    SSL_PORTS = {443, 8443, 9443}

    if ip.port:
        start = time.perf_counter()
        use_ssl = ip.port in SSL_PORTS

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(ip.timeout_seconds)

            if use_ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                with context.wrap_socket(sock, server_hostname=ip.ip_address) as ssock:
                    ssock.connect((ip.ip_address, ip.port))
            else:
                sock.connect((ip.ip_address, ip.port))

            res = {"ip": ip.ip_address, "port": ip.port, "status": "UP"}

        except socket.timeout:
            res = {
                "ip": ip.ip_address,
                "port": ip.port,
                "status": "DOWN",
                "error": f"Timed out after {ip.timeout_seconds}s",
            }

        except (ssl.SSLError, socket.error) as e:
            res = {
                "ip": ip.ip_address,
                "port": ip.port,
                "status": "DOWN",
                "error": str(e),
            }

        finally:
            sock.close()

        response_time_ms = round((time.perf_counter() - start) * 1000, 2)

        try:
            monitor_check = MonitorCheck.objects.create(
                user=ip.user,
                target_type="IP",
                ip_address=ip,
                status=res["status"],
                response_time_ms=response_time_ms,
                error_message=res.get("error", ""),
            )
        except Exception as e:
            logger.error(
                f"Failed to create MonitorCheck for IP {ip.ip_address}:{ip.port} - {str(e)}"
            )

        logger.info(f"Ping result for IP {ip.ip_address}:{ip.port}: {res}")
        return res

    param = "-n" if platform.system().lower() == "windows" else "-c"
    response_time_ms = None

    try:
        result = subprocess.run(
            ["ping", param, "1", ip.ip_address],
            stdout=subprocess.PIPE,
            timeout=ip.timeout_seconds,
        )

        if result.returncode == 0:
            res = {"ip": ip.ip_address, "status": "UP"}
            match = re.search(r"time=(\d+\.?\d*)", result.stdout.decode())

            if match:
                response_time_ms = float(match.group(1))
        else:
            res = {
                "ip": ip.ip_address,
                "status": "DOWN",
                "error": result.stdout.decode(),
            }
    except subprocess.TimeoutExpired:
        response_time_ms = ip.timeout_seconds * 1000
        res = {
            "ip": ip.ip_address,
            "status": "DOWN",
            "error": f"Ping timeout after {ip.timeout_seconds} seconds",
        }

    try:
        monitor_check = MonitorCheck.objects.create(
            user=ip.user,
            target_type="IP",
            ip_address=ip,
            status=res["status"],
            response_time_ms=response_time_ms,
            error_message=res.get("error", ""),
        )
    except Exception as e:
        logger.error(f"Failed to create MonitorCheck for IP {ip.ip_address}: {str(e)}")

    logger.info(f"Ping result for IP {ip.ip_address}: {res}")
    return res


@shared_task(name="monitoring.tasks.check_endpoint")
def check_endpoint(endpoint_id):
    close_old_connections()
    try:
        endpoint = Endpoint.objects.select_related("user").get(id=endpoint_id)
    except Endpoint.DoesNotExist:
        logger.warning("Endpoint not found")
        return "Endpoint not found"

    if not endpoint.is_active:
        msg = f"Monitoring stopped for Endpoint: {endpoint.url}"
        logger.info(msg)
        return msg

    response = None
    response_time_ms = None

    try:
        # Build request parameters
        request_kwargs = {
            "method": endpoint.http_method,
            "url": endpoint.url,
            "timeout": endpoint.timeout_seconds,
        }

        # Add headers only if they exist
        if endpoint.request_headers:
            request_kwargs["headers"] = endpoint.request_headers

        # Add body only if it exists
        if endpoint.request_body:
            request_kwargs["json"] = endpoint.request_body

        response = requests.request(**request_kwargs)
        response_time_ms = round(response.elapsed.total_seconds() * 1000, 2)

        if response.status_code == endpoint.expected_status_code:
            res = {"url": endpoint.url, "status": "UP"}
        else:
            res = {
                "url": endpoint.url,
                "status": "DOWN",
                "error": f"Expected {endpoint.expected_status_code}, got {response.status_code}",
            }
    except requests.RequestException as e:
        res = {"url": endpoint.url, "status": "DOWN", "error": str(e)}

    try:
        monitor_check = MonitorCheck.objects.create(
            user=endpoint.user,
            target_type="ENDPOINT",
            endpoint=endpoint,
            status=res["status"],
            response_time_ms=response_time_ms,
            error_message=res.get("error", ""),
        )
    except Exception as e:
        logger.error(
            f"Failed to create MonitorCheck for Endpoint {endpoint.url}: {str(e)}"
        )

    logger.info(f"Check result for Endpoint {endpoint.url}: {res}")
    return res


@shared_task(name="monitoring.tasks.hourly_aggregate_and_cleanup")
def hourly_aggregate_and_cleanup():
    close_old_connections()
    # Only touch pings older than 1 hour
    cutoff = timezone.now() - timedelta(minutes=8)
    logger.info(f"Aggregate cutoff: {cutoff}")

    # Use a datetime for filtering (not string)
    old_pings = MonitorCheck.objects.filter(checked_at__lt=cutoff)
    logger.info(f"Found old pings count: {old_pings.count()}")

    if not old_pings.exists():
        result = "no pings older than 1 hour"
        logger.info(f"Returning: {result}")
        return result

    created_hours = []

    # Separate IP and ENDPOINT records and aggregate each appropriately
    ip_pings = old_pings.filter(target_type="IP")
    if ip_pings.exists():
        aggregated_ip = ip_pings.values("user", "ip_address").annotate(
            total=Count("id"),
            up_count=Count("id", filter=Q(status="UP")),
            down_count=Count("id", filter=Q(status="DOWN")),
            avg_rt=Avg("response_time_ms"),
        )

        for entry in aggregated_ip:
            obj, _ = HourlyStat.objects.update_or_create(
                user_id=entry.get("user"),
                endpoint_id=None,
                ip_address_id=entry.get("ip_address"),
                hour=cutoff,
                defaults={
                    "target_type": "IP",
                    "total_checks": entry["total"],
                    "up_count": entry["up_count"],
                    "down_count": entry["down_count"],
                    "avg_response_time_ms": entry["avg_rt"] or 0,
                    "uptime_percent": round(
                        entry["up_count"] / entry["total"] * 100, 2
                    ),
                },
            )
            created_hours.append(obj.id)

    endpoint_pings = old_pings.filter(target_type="ENDPOINT")
    if endpoint_pings.exists():
        aggregated_ep = endpoint_pings.values("user", "endpoint").annotate(
            total=Count("id"),
            up_count=Count("id", filter=Q(status="UP")),
            down_count=Count("id", filter=Q(status="DOWN")),
            avg_rt=Avg("response_time_ms"),
        )

        for entry in aggregated_ep:
            obj, _ = HourlyStat.objects.update_or_create(
                user_id=entry.get("user"),
                endpoint_id=entry.get("endpoint"),
                ip_address_id=None,
                hour=cutoff,
                defaults={
                    "target_type": "ENDPOINT",
                    "total_checks": entry["total"],
                    "up_count": entry["up_count"],
                    "down_count": entry["down_count"],
                    "avg_response_time_ms": entry["avg_rt"] or 0,
                    "uptime_percent": round(
                        entry["up_count"] / entry["total"] * 100, 2
                    ),
                },
            )
            created_hours.append(obj.id)

    logger.info(f"Created/updated hourly stats for {len(created_hours)} hour(s)")
    result = f"Aggregated {len(created_hours)} hourly stat(s)"
    logger.info(f"Returning: {result}")

    # Delete aggregated MonitorCheck rows (those older than cutoff) inside a transaction
    deleted_count = 0
    if created_hours:
        try:
            with transaction.atomic():
                deleted_count, _ = old_pings.delete()
                logger.info(f"Deleted {deleted_count} aggregated MonitorCheck rows")
        except Exception as e:
            logger.error(f"Failed to delete aggregated MonitorCheck rows: {e}")
    result = f"Aggregated {len(created_hours)} hourly stat(s) and deleted {deleted_count} MonitorCheck rows"
    logger.info(f"Returning: {result}")
    return result


@shared_task(name="monitoring.tasks.daily_aggregate_and_cleanup")
def daily_aggregate_and_cleanup():
    close_old_connections()
    # Aggregate hourly stats older than 24 hours into daily stats
    cutoff = timezone.now() - timedelta(minutes=24)
    logger.info(f"Daily aggregate cutoff: {cutoff}")

    old_hourly = HourlyStat.objects.filter(hour__lt=cutoff)
    logger.info(f"Found old hourly stats count: {old_hourly.count()}")

    if not old_hourly.exists():
        result = "no hourly stats older than 24 hours"
        logger.info(f"Returning: {result}")
        return result

    created_days = []

    # Aggregate per user + ip + day
    ip_groups = old_hourly.filter(target_type="IP")
    if ip_groups.exists():
        aggregated_ip = (
            ip_groups.annotate(
                weighted_rt=F("avg_response_time_ms") * F("total_checks")
            )
            .values("user", "ip_address")
            .annotate(
                sum_total_checks=Sum("total_checks"),
                sum_up_count=Sum("up_count"),
                sum_down_count=Sum("down_count"),
                weighted_rt_sum=Sum("weighted_rt"),
                hours_count=Count("id"),
            )
        )

        for entry in aggregated_ip:
            total = entry["sum_total_checks"] or 0
            up = entry["sum_up_count"] or 0
            down = entry["sum_down_count"] or 0
            weighted_sum = entry.get("weighted_rt_sum") or 0
            avg_rt = (weighted_sum / total) if total else 0

            obj, _ = DailyStat.objects.update_or_create(
                user_id=entry["user"],
                endpoint_id=None,
                ip_address_id=entry.get("ip_address"),
                day=cutoff,
                defaults={
                    "target_type": "IP",
                    "total_checks": total,
                    "up_count": up,
                    "down_count": down,
                    "avg_response_time_ms": float(avg_rt),
                    "uptime_percent": round((up / total * 100), 2) if total else 0,
                },
            )
            created_days.append(obj.id)

    # Aggregate per user + endpoint + day
    ep_groups = old_hourly.filter(target_type="ENDPOINT")
    if ep_groups.exists():
        aggregated_ep = (
            ep_groups.annotate(
                weighted_rt=F("avg_response_time_ms") * F("total_checks")
            )
            .values("user", "endpoint")
            .annotate(
                sum_total_checks=Sum("total_checks"),
                sum_up_count=Sum("up_count"),
                sum_down_count=Sum("down_count"),
                weighted_rt_sum=Sum("weighted_rt"),
                hours_count=Count("id"),
            )
        )

        for entry in aggregated_ep:
            total = entry["sum_total_checks"] or 0
            up = entry["sum_up_count"] or 0
            down = entry["sum_down_count"] or 0
            weighted_sum = entry.get("weighted_rt_sum") or 0
            avg_rt = (weighted_sum / total) if total else 0

            obj, _ = DailyStat.objects.update_or_create(
                user_id=entry["user"],
                endpoint_id=entry.get("endpoint"),
                ip_address_id=None,
                day=cutoff,
                defaults={
                    "target_type": "ENDPOINT",
                    "total_checks": total,
                    "up_count": up,
                    "down_count": down,
                    "avg_response_time_ms": float(avg_rt),
                    "uptime_percent": round((up / total * 100), 2) if total else 0,
                },
            )
            created_days.append(obj.id)

    logger.info(f"Created/updated daily stats for {len(created_days)} day(s)")

    # Delete aggregated hourly stats inside a transaction to avoid partial deletes
    try:
        with transaction.atomic():
            deleted_count, _ = old_hourly.delete()
            logger.info(f"Deleted {deleted_count} old HourlyStat rows")
    except Exception as e:
        logger.error(f"Failed to delete old HourlyStat rows: {e}")

    result = f"Aggregated {len(created_days)} daily stat(s) and deleted {deleted_count if 'deleted_count' in locals() else 0} hourly rows"
    logger.info(f"Returning: {result}")
    return result
