from django import forms
from django.contrib.auth.password_validation import validate_password

from .models import User


class UserCreateForm(forms.Form):
    """Fields for the add-user page.

    Shapes the UI only — it hides the SUPERADMIN option from non-super-admins
    and checks the two passwords agree. The real rules (who may create which
    role, email uniqueness) live in ``services.create_account``.
    """

    email = forms.EmailField()
    role = forms.ChoiceField(choices=User.Role.choices)
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        if not actor.is_superadmin:
            self.fields["role"].choices = [
                (value, label)
                for value, label in User.Role.choices
                if value != User.Role.SUPERADMIN
            ]

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords don't match.")
        if password1:
            try:
                validate_password(password1)
            except forms.ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned


class UserEditForm(forms.Form):
    """Fields for the edit-user page: role and active flag only.

    Like :class:`UserCreateForm` this only shapes the UI — the SUPERADMIN
    option is hidden from non-super-admins and your own role is locked.
    ``services.update_account`` is what actually enforces the rules.
    """

    role = forms.ChoiceField(choices=User.Role.choices)
    is_active = forms.BooleanField(required=False)

    def __init__(self, *args, actor, target, **kwargs):
        kwargs.setdefault("initial", {})
        kwargs["initial"].setdefault("role", target.role)
        kwargs["initial"].setdefault("is_active", target.is_active)
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.target = target
        if not actor.is_superadmin:
            self.fields["role"].choices = [
                (value, label)
                for value, label in User.Role.choices
                if value != User.Role.SUPERADMIN
            ]
        if actor == target:
            self.fields["role"].disabled = True
