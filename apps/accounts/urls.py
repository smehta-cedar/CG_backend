from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("", views.IndexView.as_view(), name="home"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("login/verify/", views.VerifyOTPView.as_view(), name="verify_otp"),
    path("login/resend/", views.ResendOTPView.as_view(), name="resend_otp"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("users/", views.UsersView.as_view(), name="users"),
    path("users/add/", views.UserAddView.as_view(), name="user_add"),
    path("users/<int:pk>/edit/", views.UserEditView.as_view(), name="user_edit"),
    path("users/<int:pk>/delete/", views.UserDeleteView.as_view(), name="user_delete"),
    path("appointments/", views.AppointmentsView.as_view(), name="appointments"),
    path("sales/", views.SalesView.as_view(), name="sales"),
    path("facebook-ads/", views.FacebookAdsView.as_view(), name="facebook_ads"),
    path("webinar-registrants/", views.WebinarRegistrantsView.as_view(), name="webinar_registrants"),
    path("twilio/", views.TwilioView.as_view(), name="twilio"),
    path("logout/", LogoutView.as_view(next_page="login"), name="logout"),
]
