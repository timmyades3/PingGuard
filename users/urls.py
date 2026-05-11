from django.urls import path
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("register/", views.RegisterAPIView.as_view(), name= "register"),
    path("verify-email/", views.VerifyEmailAPIView.as_view(), name= "verify-email"),
    path("request-otp/", views.RequestOTPAPIView.as_view(), name= "request-otp"),
    path("login/",views.LoginAPIView.as_view(),name="login"),
    path("profile/", views.UserProfileAPIView.as_view(), name = "profile"),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path("logout/", views.LogoutAPIView.as_view(), name = "logout"),
    path('password-reset/<uidb64>/<token>/', views.PasswordTokenCheckAPIView.as_view(), name = 'password-reset-confirm'),
    path('request-reset-email', views.RequestPasswordResetEmailAPIView.as_view(), name = 'request-reset-email'),
    path('password-reset-complete/', views.SetNewPasswordAPIView.as_view(), name = 'password-reset-complete'),


]