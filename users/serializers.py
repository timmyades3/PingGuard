from rest_framework import serializers
from users.models import User, EmailVerificationOTP
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_encode,urlsafe_base64_decode
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework_simplejwt.tokens import RefreshToken,TokenError


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "email",]


class RegisterSerilizer(serializers.ModelSerializer):
    password = serializers.CharField(min_length=6, max_length=68, write_only=True)

    default_error_message = {
        "username": "The username should only contain alphanumeric characters"
    }

    class Meta:
        model = User
        fields = ["email", "username", "password"]

    def validate(self, attrs):
        email = attrs.get("email", "")
        username = attrs.get("username", "")

        if not username.isalnum():
            raise serializers.ValidationError(self.default_error_messages)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class EmailVerificationSerializer(serializers.ModelSerializer):
    otp = serializers.CharField(max_length=6)
    email = serializers.EmailField(max_length=255, min_length=3 )
    class Meta:
        model = EmailVerificationOTP
        fields = ["otp","email"]


class RequestOTPSerializer(serializers.Serializer):
    email =  serializers.EmailField(max_length = 255, min_length = 3)


class LoginSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length=255, min_length=3)
    password = serializers.CharField(max_length=68, min_length=6, write_only=True)
    username = serializers.CharField(max_length=255, min_length=3, read_only=True)
    tokens = serializers.SerializerMethodField(read_only=True)

    class Meta:
            model = User
            fields = ["email", "password", "username", "tokens"]

    def get_tokens(self, obj):
        user = User.objects.get(email=obj["email"])
        return {"access": user.tokens()["access"], "refresh": user.tokens()["refresh"]}

    def validate(self, attrs):
        email = attrs.get("email", "")
        password = attrs.get("password", "")
        user = authenticate(email=email, password=password)

        if not user:
            raise AuthenticationFailed("invalid credentials")
        if not user.is_active:
            raise AuthenticationFailed("Account disabled contact admin ")
        if not user.is_verified:
            raise AuthenticationFailed("Email is not verified")

        tokens = user.tokens()

        return {"email": user.email, "username": user.username, "tokens": tokens}


class ResetPasswordEmailRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length = 255, min_length = 2)  
    redirect_url = serializers.CharField(max_length = 500, required = False)

    class Meta:
        fields = ["email"]


class SetNewPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(max_length = 68, min_length = 6, write_only = True)
    token = serializers.CharField(min_length = 1, write_only = True)
    uidb64 = serializers.CharField(min_length = 1, write_only = True)

    class Meta:
        fields = ["password", "token","uidb64"]

    def validate(self, attrs):
        try: 
            password = attrs.get("password")
            token = attrs.get("token")
            uidb64 = attrs.get("uidb64")
            
            id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=id)

            if not PasswordResetTokenGenerator().check_token(user,token):
                raise AuthenticationFailed("the reset link invalid",401)
            user.set_password(password)
            user.save()
            return user
        except  Exception as e:
            raise AuthenticationFailed("the reset link invalid",401)
        return super().validate(attrs)

class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    default_error_messages = {
        "bad_token": ("token is expired or invalid")   
          }

    def validate(self, attrs):
        self.token = attrs["refresh"]
        return attrs
    def save(self, **kwarg) :
        try:
            RefreshToken(self.token).blacklist()
        except TokenError: 
            self.fail("bad_token")   