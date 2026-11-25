from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import User


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "accounts-tests",
        }
    }
)
class AccountApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.password = "Valid-password-481!Card"

    def test_register_and_read_or_update_own_profile(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "Rider@example.com",
                "display_name": "Rider",
                "password": self.password,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["email"], "rider@example.com")
        self.assertNotIn("password", response.data)

        user = User.objects.get(email="rider@example.com")
        self.client.force_authenticate(user=user)
        profile = self.client.get("/api/v1/auth/me/")
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["display_name"], "Rider")

        updated = self.client.patch(
            "/api/v1/auth/me/", {"display_name": "Rider One"}, format="json"
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["display_name"], "Rider One")
        self.assertNotIn("password", updated.data)

    def test_profile_requires_authentication(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_login_sets_http_only_refresh_cookie_and_logout_revokes_it(self):
        user = User.objects.create_user(
            email="player@example.com",
            password=self.password,
            display_name="Player",
        )
        client = self.client_class(enforce_csrf_checks=True)
        csrf_response = client.get("/api/v1/auth/csrf/")
        csrf_token = csrf_response.json()["csrfToken"]

        login = client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": self.password},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(login.status_code, 200)
        self.assertIn("access", login.json())
        self.assertNotIn("refresh", login.json())
        self.assertTrue(login.cookies["refresh_token"]["httponly"])

        refresh = client.post(
            "/api/v1/auth/refresh/",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(refresh.status_code, 200)
        self.assertIn("access", refresh.json())
        self.assertTrue(refresh.cookies["refresh_token"]["httponly"])

        logout = client.post(
            "/api/v1/auth/logout/",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(client.cookies["refresh_token"].value, "")

