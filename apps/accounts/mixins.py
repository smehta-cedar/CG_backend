from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


class RoleRequiredMixin(LoginRequiredMixin):
    """Gate a whole page behind one or more ``User.Role`` values.

    Subclasses ``LoginRequiredMixin`` so a view needs only this one mixin:
    anonymous visitors are still bounced to the login page first, and only
    signed-in users with the wrong role get the error-and-redirect below.

    This gates the *page* only. Per-object rules — e.g. an ADMIN may not
    modify a SUPERADMIN account — belong in ``accounts.services``, next to
    the operation they protect.
    """

    allowed_roles = ()
    role_denied_message = "You don't have access to that page."
    role_denied_redirect = "dashboard"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in self.allowed_roles:
            messages.error(request, self.role_denied_message)
            return redirect(self.role_denied_redirect)
        return super().dispatch(request, *args, **kwargs)
