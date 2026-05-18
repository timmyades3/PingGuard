from django.shortcuts import render
from rest_framework import viewsets,permissions, status
from .permissions import IsOwner
from .models import Group, IpAddress, Endpoint
from .serializers import GroupSerializer, IpAddressSerializer, EndpointSerializer
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

# Create your views here.

class GroupViewSet(viewsets.ModelViewSet):
    serializer_class = GroupSerializer
    permission_classes = (permissions.IsAuthenticated,IsOwner)
    queryset = Group.objects.all()

    def get_queryset(self):
        return Group.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)



class IPAddressViewset(viewsets.ModelViewSet):
    serializer_class = IpAddressSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    queryset = IpAddress.objects.all()

    def get_queryset(self):
        return IpAddress.objects.filter(user = self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class EndpointViewset(viewsets.ModelViewSet):
    serializer_class = EndpointSerializer
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    queryset = Endpoint.objects.all()

    def get_queryset(self):
        return Endpoint.objects.filter(user = self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class GroupEnpointIpAddressAPIView(APIView):
    permission_classes = (permissions.IsAuthenticated, IsOwner)
    group_id_param_config = openapi.Parameter('group_id',in_=openapi.IN_QUERY,description='description',type=openapi.TYPE_INTEGER)
    @swagger_auto_schema(manual_parameters=[group_id_param_config])

    def get(self, request):
        try:
            group_id = request.GET.get("group_id")
            group  =  Group.objects.get(id  = group_id, user = request.user)
        except Group.DoesNotExist:
            return Response({"detail": "Group not found."}, status=status.HTTP_404_NOT_FOUND)  

        endpoint = Endpoint.objects.filter(group = group)
        ip_address = IpAddress.objects.filter(group = group)

        endpoint_data = EndpointSerializer(endpoint, many = True).data
        ip_address_data = IpAddressSerializer(ip_address, many = True).data

        for endpoint in endpoint_data:
            endpoint["type"] = "endpoint"
        for ip_address in ip_address_data:
            ip_address["type"] = "ip"  
        data  = endpoint_data + ip_address_data
        return Response(data, status=status.HTTP_200_OK)      
    