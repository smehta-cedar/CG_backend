from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from . import services
from .forms import UserCreateForm, UserEditForm
from .mixins import RoleRequiredMixin
from .models import User


class IndexView(TemplateView):
    template_name = "index.html"


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"


class UsersView(RoleRequiredMixin, TemplateView):
    """The user-management table. Role-gated to ADMIN and SUPERADMIN;
    create, edit and deactivate land in later steps."""

    allowed_roles = (User.Role.SUPERADMIN, User.Role.ADMIN)
    template_name = "users.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["users_list"] = services.list_users()
        return context


class UserAddView(RoleRequiredMixin, View):
    """Create a new account. The form shapes the choices; ``services``
    enforces them."""

    allowed_roles = (User.Role.SUPERADMIN, User.Role.ADMIN)
    template_name = "user_form.html"

    def get(self, request):
        form = UserCreateForm(actor=request.user)
        return render(request, self.template_name, self.context(form))

    def post(self, request):
        form = UserCreateForm(request.POST, actor=request.user)
        if not form.is_valid():
            return render(request, self.template_name, self.context(form))

        data = form.cleaned_data
        try:
            user = services.create_account(
                request.user, data["email"], data["role"], data["password1"]
            )
        except services.UserAdminError as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, self.context(form))

        messages.success(request, f"Account created for {user.email}.")
        return redirect("users")

    def context(self, form):
        return {
            "form": form,
            "page_heading": "Add user",
            "submit_label": "Create account",
        }


class UserEditView(RoleRequiredMixin, View):
    """Change an account's role or active flag. The form shapes the choices;
    ``services`` enforces them."""

    allowed_roles = (User.Role.SUPERADMIN, User.Role.ADMIN)
    template_name = "user_edit_form.html"

    def get(self, request, pk):
        target = self.target_or_none(request, pk)
        if target is None:
            return redirect("users")
        form = UserEditForm(actor=request.user, target=target)
        return render(request, self.template_name, self.context(form, target))

    def post(self, request, pk):
        target = self.target_or_none(request, pk)
        if target is None:
            return redirect("users")
        form = UserEditForm(request.POST, actor=request.user, target=target)
        if not form.is_valid():
            return render(request, self.template_name, self.context(form, target))

        data = form.cleaned_data
        try:
            services.update_account(request.user, target, data["role"], data["is_active"])
        except services.UserAdminError as exc:
            messages.error(request, str(exc))
            return render(request, self.template_name, self.context(form, target))

        messages.success(request, f"Changes saved for {target.email}.")
        return redirect("users")

    def target_or_none(self, request, pk):
        """Look up the account, queuing an error message when it can't be edited."""
        target = services.get_account(pk)
        if target is None:
            messages.error(request, "That account no longer exists.")
            return None
        if target.is_superadmin and not request.user.is_superadmin:
            messages.error(request, "Only a super admin can modify super admin accounts.")
            return None
        return target

    def context(self, form, target):
        return {
            "form": form,
            "target": target,
            "page_heading": "Edit user",
            "submit_label": "Save changes",
        }


class UserDeleteView(RoleRequiredMixin, View):
    """Confirm, then permanently delete an account. ``services`` enforces
    who may delete whom; this view pre-checks so the confirm page never
    shows for an operation that can only fail."""

    allowed_roles = (User.Role.SUPERADMIN, User.Role.ADMIN)
    template_name = "user_confirm_delete.html"

    def get(self, request, pk):
        target = self.target_or_none(request, pk)
        if target is None:
            return redirect("users")
        return render(request, self.template_name, {"target": target})

    def post(self, request, pk):
        target = self.target_or_none(request, pk)
        if target is None:
            return redirect("users")

        email = target.email
        try:
            services.delete_account(request.user, target)
        except services.UserAdminError as exc:
            messages.error(request, str(exc))
            return redirect("users")

        messages.success(request, f"Deleted {email}.")
        return redirect("users")

    def target_or_none(self, request, pk):
        """Look up the account, queuing an error message when it can't be deleted."""
        target = services.get_account(pk)
        if target is None:
            messages.error(request, "That account no longer exists.")
            return None
        if target.is_superadmin and not request.user.is_superadmin:
            messages.error(request, "Only a super admin can delete super admin accounts.")
            return None
        if target == request.user:
            messages.error(
                request,
                "You can't delete your own account. Ask another admin, or deactivate it instead.",
            )
            return None
        return target


class AppointmentsView(LoginRequiredMixin, TemplateView):
    """Stub so the page is reachable. No context yet — the template renders a
    static placeholder table. Role gating and the queryset land with CRUD."""

    template_name = "appointments.html"


class SalesView(LoginRequiredMixin, View):
    """Static sales entry form. GET renders the form; POST acknowledges the
    submission with JSON so the page's fetch() can show success/error.
    Nothing is stored yet — there is no Sale model and no upload handling."""

    required_fields = ("last", "first", "count", "state", "lead_source")

    def get(self, request):
        return render(request, "sales.html")

    def post(self, request):
        missing = [f for f in self.required_fields if not request.POST.get(f, "").strip()]
        if missing:
            return JsonResponse({"ok": False, "missing": missing}, status=400)
        return JsonResponse({"ok": True})


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
