"""OTP email-login logic.

Everything about issuing, expiring and checking a sign-in code lives here so
the views only have to translate an HTTP request into one of these calls.
"""

import secrets
from datetime import timedelta
from hmac import compare_digest

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import OTPToken, User

CODE_LENGTH = 6
CODE_TTL = timedelta(minutes=5)
MAX_ATTEMPTS = 3

# Where the pending email address is parked between step 1 and step 2.
SESSION_KEY = "otp_login_email"


class OTPError(Exception):
    """A code could not be verified. ``str(exc)`` is safe to show the user."""


def _generate_code():
    """A zero-padded 6-digit code from a cryptographically secure source."""
    return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"


def _find_user(email):
    email = User.objects.normalize_email((email or "").strip())
    if not email:
        return None
    return User.objects.filter(email__iexact=email, is_active=True).first()


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


def issue_otp(email):
    """Create a fresh code for ``email`` and send it.

    Returns the matching :class:`~accounts.models.User`, or ``None`` when no
    active account has that address.
    """
    user = _find_user(email)
    if user is None:
        return None

    # Retire anything still outstanding so only the newest code is accepted.
    OTPToken.objects.filter(user=user, is_used=False).update(is_used=True)

    token = OTPToken.objects.create(user=user, code=_generate_code())
    _send_code(user, token.code)
    return user


def verify_otp(email, code):
    """Return the user behind a valid code, or raise :class:`OTPError`.

    A code passes only when it is the newest outstanding one for the account,
    is under :data:`CODE_TTL` old, has not been used, and has not already
    burned through :data:`MAX_ATTEMPTS` wrong guesses.
    """
    user = _find_user(email)
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


def _burn(token):
    token.is_used = True
    token.save(update_fields=["is_used"])


def mask_email(email):
    """``alex@cedargrove.io`` -> ``al••@cedargrove.io``, for the verify screen."""
    local, _, domain = (email or "").partition("@")
    if not domain:
        return email
    shown = local[:2]
    return f"{shown}{'•' * max(len(local) - len(shown), 1)}@{domain}"
