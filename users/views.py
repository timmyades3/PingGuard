from django.urls import reverse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from .serializers import *
from .renderers import UserRender
from .models import EmailVerificationOTP, User
from drf_yasg.utils import swagger_auto_schema
from .utils import create_otp_for_user, generate_otp, Util
from drf_yasg import openapi
from django.utils import timezone
from datetime import timedelta
from django.utils.encoding import smart_str, smart_bytes, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_decode
from django.http import HttpResponseRedirect
from decouple import config
from django.contrib.sites.shortcuts import get_current_site
from rest_framework.permissions import IsAuthenticated


class CustomRedirect(HttpResponseRedirect):
    allowed_schemes = [config("APP_SCHEME"), "http", "https"]



class RegisterAPIView(generics.GenericAPIView):

    serializer_class = RegisterSerilizer
    renderer_classes = (UserRender,)

    @swagger_auto_schema(
        operation_summary="register a new user",
        operation_description="""
        Register a new user and send OTP to email.
        
        Returns:
        - user data with success message
        - OTP expires in 10 minutes
        """,
    )
    def post(self, request):
        # register a new user
        user = request.data
        serializer = self.serializer_class(data=user)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        user_data = serializer.data

        # Create OTP for email verification
        try:
            user_obj = serializer.instance 
            otp_record = create_otp_for_user(user_obj)
            email_body = "hi " + user_obj.username + " use OTP bellow to verify your email \n" +otp_record.otp
            data = {"email_body":email_body,"to_email":user_obj.email, "email_subject": "verify your email"}
            Util.send_email(data)
            user_data["message"] = "User registered successfully. OTP sent to email."
            user_data["otp_expires_in_minutes"] = 10
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(user_data, status=status.HTTP_201_CREATED)


class VerifyEmailAPIView(generics.GenericAPIView):
    # Verify OTP and mark user as verified

    serializer_class = EmailVerificationSerializer

    @swagger_auto_schema(
        operation_summary="Verify user email with OTP",
    )
    def post(self, request):
        otp = request.data.get("otp")
        email = request.data.get("email")

        if not otp or not email:
            return Response(
                {"error": "OTP and user email are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:

            otp_record = EmailVerificationOTP.objects.get(
                otp=otp, user__email=email, is_used=False
            )

            # Check if OTP is expired
            if timezone.now() > otp_record.expires_at:
                return Response(
                    {"error": "OTP has expired"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Mark OTP as used and user as verified
            otp_record.is_used = True
            otp_record.save()

            user = otp_record.user
            user.is_verified = True
            user.save()

            return Response(
                {
                    "message": "Email verified successfully",
                },
                status=status.HTTP_200_OK,
            )

        except EmailVerificationOTP.DoesNotExist:
            return Response(
                {"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST
            )


class RequestOTPAPIView(generics.GenericAPIView):
    serializer_class = RequestOTPSerializer

    @swagger_auto_schema(
        operation_summary="Request for a new OTP",
    )
    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
            if user.is_verified == True:
                return Response(
                    {"error": "User is already verified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Get existing OTP or create new one
            otp_record = EmailVerificationOTP.objects.filter(
                user=user, is_used=False
            ).first()

            if otp_record and timezone.now() < otp_record.expires_at:
                return Response(
                    {
                        "error": "current OTP is this active. Requset for another OTP after 10 mins"
                    }
                )
            if otp_record:
                # Update existing OTP

                otp_record.otp = generate_otp()
                otp_record.created_at = timezone.now()
                otp_record.expires_at = timezone.now() + timedelta(minutes=10)
                otp_record.save()
                
                email_body = "hi " + user.username + " use OTP bellow to verify your email \n" +otp_record.otp
                data = {"email_body":email_body,"to_email":user.email, "email_subject": "verify your email"}
                Util.send_email(data)

            else:
                # send error if no user found with email
                return Response(
                    {"error": "No user found with this email try registering first"},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {"message": "OTP sent to email and expires in 10 min"},
                status=status.HTTP_200_OK,
            )

        except User.DoesNotExist:
            return Response(
                {"error": "User does not exist"}, status=status.HTTP_404_NOT_FOUND
            )


class LoginAPIView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    renderer_classes = (UserRender,)

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data, status=status.HTTP_200_OK)

class UserProfileAPIView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated,]

    def get_object(self):
        return self.request.user


class RequestPasswordResetEmailAPIView(generics.GenericAPIView):
    serializer_class = ResetPasswordEmailRequestSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        email = request.data.get("email")

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email=email)
            uidb64 = urlsafe_base64_encode(smart_bytes(user.id))
            token = PasswordResetTokenGenerator().make_token(user)
            current_site = get_current_site(request).domain
            relativeLink = reverse('password-reset-confirm',kwargs={'uidb64': uidb64, 'token':token })
            absurl = 'http://'+current_site+relativeLink
            redirect_url= request.data.get('redirect_url', '')    
            email_body = 'hello, \n use link bellow to reset your password \n' + absurl+"?redirect_url="+redirect_url
            data = {'email_body':email_body, 'to_email':user.email, 'email_subject':"Reset your password"}
            Util.send_email(data) 

        return Response(
            {"message": "we have sent you the link to reset your password "},
            status=status.HTTP_200_OK,
        )


class PasswordTokenCheckAPIView(generics.GenericAPIView):
    serializer_class = SetNewPasswordSerializer

    def get(self, request, uidb64, token):
        redirect_url = request.GET.get("redirect_url")
        try:
            id = smart_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=id)

            if not PasswordResetTokenGenerator().check_token(user, token):
                if len(redirect_url) > 3:
                    return CustomRedirect(redirect_url + "?token_valid = false")
                else:
                    return CustomRedirect(
                        config("FRONTEND_URL", "") + "?token_valid = false"
                    )

            if redirect_url and len(redirect_url) > 3:
                return CustomRedirect(
                    redirect_url
                    + "?token_valid=True&message=Credentials Valid&uidb64="
                    + uidb64
                    + "&token="
                    + token
                )
            else:
                return CustomRedirect(config("FRONTEND_URL", "") + "?token_valid=False")

        except DjangoUnicodeDecodeError as identifier:
            try:
                if not PasswordResetTokenGenerator().check_token(user):
                    return CustomRedirect(redirect_url + "?token_valid=False")

            except UnboundLocalError as e:
                return Response(
                    {"error": "Token is not valid, please request a new one"},
                    status=status.HTTP_400_BAD_REQUEST,
                )


class SetNewPasswordAPIView(generics.GenericAPIView):
    serializer_class = SetNewPasswordSerializer

    def patch(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "message": True,
                "mesaage": "Password reset success",
            },
            status=status.HTTP_200_OK,
        )


class LogoutAPIView(generics.GenericAPIView):
    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated,]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "You have logged out successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )
