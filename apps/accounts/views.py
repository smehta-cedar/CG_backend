from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from . import services


class IndexView(TemplateView):
    template_name = "index.html"


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"


class UsersView(LoginRequiredMixin, TemplateView):
    """Stub so the page is reachable. No context yet — the template renders a
    static placeholder table. Role gating and the queryset land with CRUD."""

    template_name = "users.html"


class AppointmentsView(LoginRequiredMixin, TemplateView):
    """Stub so the page is reachable. No context yet — the template renders a
    static placeholder table. Role gating and the queryset land with CRUD."""

    template_name = "appointments.html"


class FacebookAdsView(LoginRequiredMixin, TemplateView):
    """Stub so the page is reachable. No context yet — the template renders a
    static placeholder table. Role gating and the queryset land with CRUD."""

    template_name = "facebook-ads.html"


class WebinarRegistrantsView(LoginRequiredMixin, TemplateView):
    """Stub so the page is reachable. No context yet — the template renders a
    static placeholder table. Role gating and the queryset land with CRUD."""

    template_name = "webinar-registrants.html"


class TwilioView(LoginRequiredMixin, TemplateView):
    """Stub so the page is reachable. No context yet — the template renders a
    static placeholder table. Role gating and the queryset land with CRUD."""

    template_name = "twilio.html"


class LoginView(View):
    """Step 1 — take an email address and mail a sign-in code to it."""

    template_name = "login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        user = services.authenticate_user(request, email, password)
        if user is None:
            messages.error(request, "Invalid email or password.")
            return render(request, "login.html", {"email": email})

        try:
            services.issue_otp(user)          # user object, not email
        except services.OTPCooldown as e:
            messages.info(request, str(e))    # still send them to verify — old code may be live
        request.session[services.SESSION_KEY] = user.email
        return redirect("verify_otp")


class VerifyOTPView(View):
    """Step 2 — check the code and, if it holds up, sign the user in."""

    template_name = "accounts/verify_otp.html"

    def get(self, request):
        email = request.session.get(services.SESSION_KEY)
        if not email:
            return redirect("login")
        return render(request, self.template_name, self.context(email))

    def post(self, request):
        email = request.session.get(services.SESSION_KEY)
        if not email:
            return redirect("login")

        try:
            user = services.verify_otp(email, request.POST.get("code", ""))
        except services.OTPError as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, self.context(email))

        login(request, user)
        request.session.pop(services.SESSION_KEY, None)
        return redirect(settings.LOGIN_REDIRECT_URL)

    def context(self, email):
        return {
            "email": email,
            "masked_email": services.mask_email(email),
            "code_length": services.CODE_LENGTH,
        }


class ResendOTPView(View):
    """Issue a replacement code for the address already held in the session."""

    def post(self, request):
        email = request.session.get(services.SESSION_KEY)
        user = services.pending_user(email) if email else None
        if user is None:
            return redirect("login")

        try:
            services.issue_otp(user)
            messages.info(request, "A new code has been sent.")
        except services.OTPError as e:      # catches OTPCooldown too
            messages.error(request, str(e))
        return redirect("verify_otp")
