from rest_framework import serializers
from .models import Group,IpAddress,Endpoint

class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
    def validate_name(self, value):
        user = self.context['request'].user
        if Group.objects.filter(user=user, name=value).exists():
            raise serializers.ValidationError("You already have a group with this name.")
        return value

class IpAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = IpAddress
        fields = ['id', 'ip_address', 'label', 'group', 'port', 'timeout_seconds', 'is_active', 'created_at', 'updated_at']

    def validate_ip_address(self, value):
        user = self.context['request'].user
        if IpAddress.objects.filter(user=user, ip_address=value).exists():
            raise serializers.ValidationError("You have already added this IP address.")
        return value

class EndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = Endpoint
        fields = ['id', 'label', 'url', 'http_method', 'group', 'expected_status_code', 'request_headers', 'request_body', 'timeout_seconds', 'expected_response_keyword', 'is_active', 'created_at', 'updated_at']


    def validate(self, attrs):
        url = attrs.get('url', None)
        http_method = attrs.get('http_method', None)
        user = self.context['request'].user
        if Endpoint.objects.filter(user=user, url=url, http_method=http_method).exists():
            raise serializers.ValidationError("You have already added this endpoint with the same HTTP method.")
        return attrs
