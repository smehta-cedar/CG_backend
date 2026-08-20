from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # apps/ is on sys.path (see config/settings/base.py), so project apps are
    # imported top-level. Label is pinned so it stays stable either way.
    name = "accounts"
    label = "accounts"
