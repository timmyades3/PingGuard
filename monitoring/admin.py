from django.contrib import admin
from .models import Group, HourlyStat, IpAddress, Endpoint, MonitorCheck, DailyStat

# Register your models here.
admin.site.register(Group)
admin.site.register(IpAddress)  
admin.site.register(Endpoint)
admin.site.register(MonitorCheck)
admin.site.register(HourlyStat)
admin.site.register(DailyStat)  