from django.contrib import admin
from .models import Group, IpAddress, Endpoint

# Register your models here.
admin.site.register(Group)
admin.site.register(IpAddress)  
admin.site.register(Endpoint)