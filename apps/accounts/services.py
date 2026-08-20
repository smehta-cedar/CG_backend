"""Two-step sign-in logic: password first, then an emailed one-time code.

Everything about authenticating, issuing, expiring and checking a code lives
here so the views only have to translate an HTTP request into one of these
calls.
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
