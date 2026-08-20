"""Two-step sign-in logic: password first, then an emailed one-time code.

Everything about authenticating, issuing, expiring and checking a code lives
here so the views only have to translate an HTTP request into one of these
calls. The same goes for user management: reading and changing accounts
happens here, never in a view.
"""

import math
import secrets
from datetime import timedelta
from hmac import compare_digest

from django.conf import settings
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.utils import timezone

from .models import OTPToken, User

CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 3
RESEND_COOLDOWN = timedelta(seconds=60)

# Where the half-authenticated email address is parked between step 1 and 2.
SESSION_KEY = "otp_login_email"


class OTPError(Exception):
    """An OTP request failed. ``str(exc)`` is safe to show the user."""


class OTPCooldown(OTPError):
    """A new code was asked for too soon after the previous one."""

    def __init__(self, seconds_remaining):
        self.seconds_remaining = seconds_remaining
        plural = "" if seconds_remaining == 1 else "s"
        super().__init__(
            f"Please wait {seconds_remaining} second{plural} "
            "before requesting another code."
        )


def authenticate_user(request, email, password):
    """Check an email/password pair. Returns the user, or ``None``.

    The caller must not reveal *which* half was wrong — see ``LoginView``.
    """
    email = User.objects.normalize_email((email or "").strip())
    user = User.objects.filter(email__iexact=email).first()
    # Hand the backend the stored spelling when we have a match so login stays
    # case-insensitive; otherwise pass the input through anyway so its dummy
    # password check still runs and a missing account takes the same time.
    return authenticate(
        request, username=user.email if user else email, password=password
    )


def pending_user(email):
    """The active user behind a half-finished sign-in, or ``None``."""
    email = User.objects.normalize_email((email or "").strip())
    if not email:
        return None
    return User.objects.filter(email__iexact=email, is_active=True).first()


def issue_otp(user):
    """Mint a fresh code for ``user`` and email it.

    Raises :class:`OTPCooldown` if one was issued less than
    :data:`RESEND_COOLDOWN` ago.
    """
    _check_cooldown(user)

    # Retire anything still outstanding so only the newest code is accepted.
    OTPToken.objects.filter(user=user, is_used=False).update(is_used=True)

    token = OTPToken.objects.create(user=user, code=_generate_code())
    _send_code(user, token.code)
    return token


def verify_otp(email, code):
    """Return the user behind a valid code, or raise :class:`OTPError`.

    A code passes only when it is the newest outstanding one for the account,
    is under :data:`CODE_TTL` old, has not been used, and has not already
    burned through :data:`MAX_ATTEMPTS` wrong guesses.
    """
    user = pending_user(email)
    if user is None:
        raise OTPError("That sign-in attempt is no longer valid. Please start again.")

    token = (
        OTPToken.objects.filter(user=user, is_used=False)
        .order_by("-created_at")
        .first()
    )
    if token is None:
        raise OTPError("That code is no longer valid. Request a new one.")

    if timezone.now() - token.created_at > CODE_TTL:
        _burn(token)
        raise OTPError("That code has expired. Request a new one.")

    submitted = (code or "").strip()
    if not compare_digest(token.code.encode(), submitted.encode()):
        token.attempts += 1
        remaining = MAX_ATTEMPTS - token.attempts
        if remaining <= 0:
            token.is_used = True
            token.save(update_fields=["attempts", "is_used"])
            raise OTPError("Too many incorrect attempts. Request a new code.")
        token.save(update_fields=["attempts"])
        raise OTPError(
            f"That code is incorrect. "
            f"{remaining} attempt{'' if remaining == 1 else 's'} remaining."
        )

    _burn(token)
    return user


def mask_email(email):
    """``alex@cedargrove.io`` -> ``al••@cedargrove.io``, for the verify screen."""
    local, _, domain = (email or "").partition("@")
    if not domain:
        return email
    shown = local[:2]
    return f"{shown}{'•' * max(len(local) - len(shown), 1)}@{domain}"


def _generate_code():
    """A zero-padded 6-digit code from a cryptographically secure source."""
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


def _check_cooldown(user):
    last = OTPToken.objects.filter(user=user).order_by("-created_at").first()
    if last is None:
        return
    elapsed = timezone.now() - last.created_at
    if elapsed < RESEND_COOLDOWN:
        left = (RESEND_COOLDOWN - elapsed).total_seconds()
        raise OTPCooldown(max(1, math.ceil(left)))


def _send_code(user, code):
    minutes = int(CODE_TTL.total_seconds() // 60)
    send_mail(
        subject="Your Cedar Grove sign-in code",
        message=(
            f"Your sign-in code is {code}\n\n"
            f"It expires in {minutes} minutes and can only be used once.\n"
            "If you didn't try to sign in, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


def _burn(token):
    token.is_used = True
    token.save(update_fields=["is_used"])


# --- User management ---


class UserAdminError(Exception):
    """A user-management request failed. ``str(exc)`` is safe to show the user."""


def list_users():
    """Every account, for the user-management table."""
    return User.objects.all()


def get_account(pk):
    """The account with this primary key, or ``None``."""
    return User.objects.filter(pk=pk).first()


def create_account(actor, email, role, password):
    """Create a new account on behalf of ``actor`` and return it.

    Every rule is enforced here, whatever the form let through: the role
    must be real, only a super admin may mint another super admin, and the
    email must not already belong to an account.

    Raises :class:`UserAdminError` when any of that fails.
    """
    if role not in User.Role.values:
        raise UserAdminError("That role is not recognised.")
    if role == User.Role.SUPERADMIN and not actor.is_superadmin:
        raise UserAdminError("Only a super admin can create super admin accounts.")

    email = User.objects.normalize_email((email or "").strip())
    if not email:
        raise UserAdminError("An email address is required.")
    if User.objects.filter(email__iexact=email).exists():
        raise UserAdminError(f"An account for {email} already exists.")

    return User.objects.create_user(email=email, password=password, role=role)


def update_account(actor, target, role, is_active):
    """Change ``target``'s role and active flag on behalf of ``actor``.

    Enforced here, whatever the form allowed: only a super admin may touch a
    super admin account or hand out that role, and nobody may change their
    own role or deactivate themselves. Email and password are not editable
    through this path.

    Raises :class:`UserAdminError` when any of that fails.
    """
    if role not in User.Role.values:
        raise UserAdminError("That role is not recognised.")
    if target.is_superadmin and not actor.is_superadmin:
        raise UserAdminError("Only a super admin can modify super admin accounts.")
    if role == User.Role.SUPERADMIN and not actor.is_superadmin:
        raise UserAdminError("Only a super admin can grant the super admin role.")
    if actor == target:
        if role != actor.role:
            raise UserAdminError("You can't change your own role.")
        if not is_active:
            raise UserAdminError("You can't deactivate your own account.")

    target.role = role
    target.is_active = bool(is_active)
    target.save(update_fields=["role", "is_active"])
    return target


def delete_account(actor, target):
    """Permanently remove ``target`` on behalf of ``actor``.

    Only a super admin may delete a super admin account, and nobody may
    delete themselves. There is no undo: the row goes, and the user's OTP
    tokens go with it (``OTPToken.user`` cascades).

    Raises :class:`UserAdminError` when either rule fails.
    """
    if target.is_superadmin and not actor.is_superadmin:
        raise UserAdminError("Only a super admin can delete super admin accounts.")
    if actor == target:
        raise UserAdminError(
            "You can't delete your own account. Ask another admin, or deactivate it instead."
        )
    target.delete()
