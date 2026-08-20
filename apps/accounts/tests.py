"""Pins the user-management rules so a refactor can't silently loosen them.

Service tests call ``accounts.services`` directly — that layer is the law.
View tests go through the test client and only check the gate (who may
reach a page) and the wiring (a valid POST really reaches the service).
"""

from django.contrib.auth import authenticate
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts import services
from accounts.models import OTPToken, User
from accounts.services import UserAdminError

PASSWORD = "correct-horse-battery-staple-42"


class AccountsTestCase(TestCase):
    """Three fixture users, one per role. Shared by every test class."""

    @classmethod
    def setUpTestData(cls):
        cls.superadmin = User.objects.create_user(
            email="super@example.com", password=PASSWORD, role=User.Role.SUPERADMIN
        )
        cls.admin = User.objects.create_user(
            email="admin@example.com", password=PASSWORD, role=User.Role.ADMIN
        )
        cls.user = User.objects.create_user(
            email="user@example.com", password=PASSWORD, role=User.Role.USER
        )


# --- Service layer ---


class CreateAccountTests(AccountsTestCase):
    def test_admin_cannot_create_superadmin(self):
        with self.assertRaises(UserAdminError):
            services.create_account(
                self.admin, "new@example.com", User.Role.SUPERADMIN, PASSWORD
            )
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_superadmin_can_create_superadmin(self):
        created = services.create_account(
            self.superadmin, "new@example.com", User.Role.SUPERADMIN, PASSWORD
        )
        self.assertTrue(created.is_superadmin)
        self.assertTrue(User.objects.filter(pk=created.pk).exists())

    def test_duplicate_email_raises(self):
        with self.assertRaises(UserAdminError):
            services.create_account(
                self.superadmin, "admin@example.com", User.Role.USER, PASSWORD
            )

    def test_duplicate_email_case_variant_raises(self):
        with self.assertRaises(UserAdminError):
            services.create_account(
                self.superadmin, "Admin@Example.com", User.Role.USER, PASSWORD
            )
        self.assertEqual(User.objects.filter(email__iexact="admin@example.com").count(), 1)

    def test_invalid_role_raises(self):
        with self.assertRaises(UserAdminError):
            services.create_account(self.superadmin, "new@example.com", "WIZARD", PASSWORD)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_success_sets_usable_password(self):
        created = services.create_account(
            self.admin, "new@example.com", User.Role.USER, PASSWORD
        )
        self.assertTrue(created.check_password(PASSWORD))
        self.assertIsNotNone(authenticate(username="new@example.com", password=PASSWORD))


class UpdateAccountTests(AccountsTestCase):
    def test_admin_cannot_edit_superadmin(self):
        with self.assertRaises(UserAdminError):
            services.update_account(self.admin, self.superadmin, User.Role.USER, True)
        self.superadmin.refresh_from_db()
        self.assertTrue(self.superadmin.is_superadmin)

    def test_admin_cannot_grant_superadmin(self):
        with self.assertRaises(UserAdminError):
            services.update_account(self.admin, self.user, User.Role.SUPERADMIN, True)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.USER)

    def test_cannot_change_own_role(self):
        with self.assertRaises(UserAdminError):
            services.update_account(self.superadmin, self.superadmin, User.Role.ADMIN, True)
        self.superadmin.refresh_from_db()
        self.assertTrue(self.superadmin.is_superadmin)

    def test_cannot_deactivate_self(self):
        with self.assertRaises(UserAdminError):
            services.update_account(self.admin, self.admin, User.Role.ADMIN, False)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_superadmin_edit_persists_role_and_is_active(self):
        services.update_account(self.superadmin, self.user, User.Role.ADMIN, False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.ADMIN)
        self.assertFalse(self.user.is_active)


class DeleteAccountTests(AccountsTestCase):
    def test_admin_cannot_delete_superadmin(self):
        with self.assertRaises(UserAdminError):
            services.delete_account(self.admin, self.superadmin)
        self.assertTrue(User.objects.filter(pk=self.superadmin.pk).exists())

    def test_cannot_delete_self(self):
        with self.assertRaises(UserAdminError):
            services.delete_account(self.superadmin, self.superadmin)
        self.assertTrue(User.objects.filter(pk=self.superadmin.pk).exists())

    def test_delete_removes_row_and_cascades_otp_tokens(self):
        OTPToken.objects.create(user=self.user, code="123456")
        pk = self.user.pk
        services.delete_account(self.superadmin, self.user)
        self.assertFalse(User.objects.filter(pk=pk).exists())
        self.assertFalse(OTPToken.objects.filter(user_id=pk).exists())


class GetAccountTests(AccountsTestCase):
    def test_missing_pk_returns_none(self):
        self.assertIsNone(services.get_account(999999))

    def test_existing_pk_returns_user(self):
        self.assertEqual(services.get_account(self.user.pk), self.user)


# --- View layer ---


class UserViewsGateTests(AccountsTestCase):
    def test_anonymous_redirects_to_login(self):
        response = self.client.get(reverse("users"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("login")))

    def test_user_role_is_bounced_to_dashboard(self):
        self.client.force_login(self.user)
        urls = [
            reverse("users"),
            reverse("user_add"),
            reverse("user_edit", args=[self.admin.pk]),
            reverse("user_delete", args=[self.admin.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_admin_cannot_open_edit_for_superadmin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("user_edit", args=[self.superadmin.pk]))
        self.assertRedirects(response, reverse("users"), fetch_redirect_response=False)

    def test_admin_cannot_open_delete_for_superadmin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("user_delete", args=[self.superadmin.pk]))
        self.assertRedirects(response, reverse("users"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(pk=self.superadmin.pk).exists())

    def test_admin_forged_superadmin_post_creates_nothing(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("user_add"),
            {
                "email": "forged@example.com",
                "role": User.Role.SUPERADMIN,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertFalse(User.objects.filter(email="forged@example.com").exists())


class UserViewsHappyPathTests(AccountsTestCase):
    def setUp(self):
        self.client.force_login(self.superadmin)

    def test_superadmin_create_edit_delete(self):
        response = self.client.post(
            reverse("user_add"),
            {
                "email": "created@example.com",
                "role": User.Role.USER,
                "password1": PASSWORD,
                "password2": PASSWORD,
            },
        )
        self.assertRedirects(response, reverse("users"), fetch_redirect_response=False)
        created = User.objects.get(email="created@example.com")
        self.assertEqual(created.role, User.Role.USER)

        response = self.client.post(
            reverse("user_edit", args=[created.pk]),
            {"role": User.Role.ADMIN},  # is_active omitted -> False
        )
        self.assertRedirects(response, reverse("users"), fetch_redirect_response=False)
        created.refresh_from_db()
        self.assertEqual(created.role, User.Role.ADMIN)
        self.assertFalse(created.is_active)

        response = self.client.post(reverse("user_delete", args=[created.pk]))
        self.assertRedirects(response, reverse("users"), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=created.pk).exists())

    def test_get_on_delete_url_does_not_delete(self):
        response = self.client.get(reverse("user_delete", args=[self.user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())


# --- Sales entry form ---


class SalesViewTests(AccountsTestCase):
    REQUIRED = {
        "last": "Doe",
        "first": "Jane",
        "state": "TX",
        "effective_date": "2026-01-15",
        "product": "MAPD",
        "company": "HUMANA",
    }

    def _pdf(self, name="ancillary.pdf"):
        return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("sales"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_get_renders_form(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("sales"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "sales.html")
        for name in (
            "last", "first", "count", "state", "lead_source", "effective_date",
            "product", "company", "aor", "dnsp", "calendar",
            "ancillary_pdf", "additional_files",
        ):
            self.assertContains(response, f'name="{name}"')
        self.assertContains(response, 'value="1"')
        self.assertContains(response, "WEBINAR")
        self.assertContains(response, "MAPD")
        self.assertContains(response, "HEALTHSRPING")
        self.assertContains(response, ">TX<")
        self.assertContains(response, "PERSONAL")

    def test_post_with_required_fields_succeeds(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("sales"),
            {**self.REQUIRED, "ancillary_pdf": self._pdf()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_post_missing_required_field_is_rejected(self):
        self.client.force_login(self.user)
        data = {**self.REQUIRED, "state": "", "ancillary_pdf": self._pdf()}
        response = self.client.post(reverse("sales"), data)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["missing"], ["state"])

    def test_post_missing_ancillary_pdf_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("sales"), self.REQUIRED)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["missing"], ["ancillary_pdf"])
