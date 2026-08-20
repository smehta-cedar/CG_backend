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


class LoginView(View):
    """Step 1 — take an email address and mail a sign-in code to it."""

    template_name = "login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get("email", "").strip()

        if services.issue_otp(email) is None:
            messages.error(request, "We don't have an account for that email address.")
            return render(request, self.template_name, {"email": email})

        request.session[services.SESSION_KEY] = email
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
        if not email:
            return redirect("login")

        if services.issue_otp(email) is None:
            request.session.pop(services.SESSION_KEY, None)
            messages.error(request, "We don't have an account for that email address.")
            return redirect("login")

        messages.success(request, "A new code is on its way.")
        return redirect("verify_otp")
