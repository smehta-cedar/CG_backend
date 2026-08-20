from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.IndexView.as_view(), name="home"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("login/verify/", views.VerifyOTPView.as_view(), name="verify_otp"),
    path("login/resend/", views.ResendOTPView.as_view(), name="resend_otp"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
]
