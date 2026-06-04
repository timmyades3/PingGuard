from django.db import models
from users.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q 
from django.db.models.signals import post_save
from django.dispatch import receiver

class Group(models.Model):
    user = models.ForeignKey(User, on_delete = models.CASCADE)
    name  = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        unique_together = ('user', 'name')  

    def __str__(self):
        return self.name
        
     
class IpAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ip_addresses')
    ip_address = models.GenericIPAddressField(protocol='both', blank=False)  
    label = models.CharField(max_length=100, blank=False)  
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True, related_name='ip_addresses')
    port = models.PositiveIntegerField(null=True, blank=True)  
    timeout_seconds = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(3), MaxValueValidator(30)]  
    )    
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'ip_address') 
        verbose_name_plural = "IP Addresses"

    def __str__(self):
        return f"{self.label} ({self.ip_address})"

class Endpoint(models.Model):
    HTTP_METHODS = [
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('HEAD', 'HEAD'), 
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='endpoints')
    label = models.CharField(max_length=100, blank=False)
    url = models.URLField(max_length=500, blank=False)
    http_method = models.CharField(choices=HTTP_METHODS, max_length=10, default='GET')
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    
    expected_status_code = models.PositiveIntegerField(default=200)
    
    # request config
    request_headers = models.JSONField(default=dict, blank=True)
    request_body = models.JSONField(default=dict, blank=True)
    timeout_seconds = models.PositiveIntegerField(
    default=10,
    validators=[MinValueValidator(3), MaxValueValidator(30)]  
)

    # optional response validation
    expected_response_keyword = models.CharField(max_length=255, blank=True, null=True)

    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('user', 'url', 'http_method')

    def __str__(self):
        return f"{self.label} ({self.url})"
    
class TargetType(models.TextChoices):
    IP = "IP", "IP Address"
    ENDPOINT = "ENDPOINT", "Endpoint"


class MonitorCheck(models.Model):
    STATUS_CHOICES = [
        ('UP', 'UP'),
        ('DOWN', 'DOWN'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='monitor_checks')
    target_type = models.CharField( max_length=10,choices=TargetType.choices)
    
    # one will be set, the other null depending on target_type
    ip_address = models.ForeignKey(IpAddress, on_delete=models.CASCADE, null=True, blank=True, related_name='checks')
    endpoint = models.ForeignKey(Endpoint, on_delete=models.CASCADE, null=True, blank=True, related_name='checks')

    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    response_time_ms = models.FloatField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-checked_at']

    def __str__(self):
        target = self.ip_address or self.endpoint
        return f"{self.target_type} | {target} | {self.status} @ {self.checked_at}"


class HourlyStat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hourly_stats')
    target_type = models.CharField(max_length=10,choices=TargetType.choices)
    ip_address = models.ForeignKey(IpAddress, on_delete=models.CASCADE, null=True, blank=True)
    endpoint = models.ForeignKey(Endpoint, on_delete=models.CASCADE, null=True, blank=True)
    hour = models.DateTimeField() 
    total_checks = models.IntegerField()
    up_count = models.IntegerField()
    down_count = models.IntegerField()
    avg_response_time_ms = models.FloatField()
    uptime_percent = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['ip_address', 'hour'],
                condition=Q(ip_address__isnull=False),
                name='unique_ip_hour'
            ),
            models.UniqueConstraint(
                fields=['endpoint', 'hour'],
                condition=Q(endpoint__isnull=False),
                name='unique_endpoint_hour'
            ),
        ]

        indexes = [
            models.Index(fields=['ip_address', 'hour']),
            models.Index(fields=['endpoint', 'hour']),
        ]
    def __str__(self):
        target = self.ip_address or self.endpoint
        return f"{self.target_type} | {target} | {self.hour}"
    
class DailyStat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_stats')
    target_type = models.CharField(max_length=10,choices=TargetType.choices)
    ip_address = models.ForeignKey(IpAddress, on_delete=models.CASCADE, null=True, blank=True)
    endpoint = models.ForeignKey(Endpoint, on_delete=models.CASCADE, null=True, blank=True)
    day = models.DateTimeField() 
    total_checks = models.IntegerField()
    up_count = models.IntegerField()
    down_count = models.IntegerField()
    avg_response_time_ms = models.FloatField()
    uptime_percent = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['ip_address', 'day'],
                condition=Q(ip_address__isnull=False),
                name='unique_ip_day'
            ),
            models.UniqueConstraint(
                fields=['endpoint', 'day'],
                condition=Q(endpoint__isnull=False),
                name='unique_endpoint_day'
            ),
        ]

        indexes = [
            models.Index(fields=['ip_address', 'day']),
            models.Index(fields=['endpoint', 'day']),
        ]
    def __str__(self):
        target = self.ip_address or self.endpoint
        return f"{self.target_type} | {target} | {self.day}"


class Incident(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'OPEN'),
        ('RESOLVED', 'RESOLVED'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='incidents')
    target_type = models.CharField(max_length=10, choices=TargetType.choices)
    ip_address = models.ForeignKey(IpAddress, on_delete=models.CASCADE, null=True, blank=True, related_name='incidents')
    endpoint = models.ForeignKey(Endpoint, on_delete=models.CASCADE, null=True, blank=True, related_name='incidents')
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='OPEN')
    started_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    last_notification_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        target = self.ip_address or self.endpoint
        return f"Incident: {self.target_type} | {target} | {self.status}"


class Settings(models.Model):   
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    notification_email = models.EmailField(max_length=255, blank=True, null=True)
    notification_interval_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MinValueValidator(5), MaxValueValidator(1440)]  
    ) 
    moniotoring_interval_seconds = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(10), MaxValueValidator(3600)]
    )

    class Meta:
        verbose_name_plural = "Settings"

    def __str__(self):
        return f"Settings for {self.user.username}"



@receiver(post_save, sender=User)
def create_user_settings(sender, instance, created, **kwargs):
    if created:
        Settings.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_settings(sender, instance, **kwargs):
    if hasattr(instance, 'settings'):
        instance.settings.save()