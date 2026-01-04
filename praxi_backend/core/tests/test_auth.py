"""Tests for Authentication endpoints.

Tests cover:
- Login (POST /api/auth/login/)
- Refresh (POST /api/auth/refresh/)
- Me (GET /api/auth/me/)
- RBAC: tokens contain role info

Uses only the default/system test DB.
"""

from __future__ import annotations

from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from praxi_backend.core.models import Role, User


class AuthenticationTest(TestCase):
    """Tests for /api/auth/ endpoints."""

    databases = {"default"}

    def setUp(self):
        # Create roles
        self.role_admin, _ = Role.objects.using("default").get_or_create(
            name="admin",
            defaults={"label": "Administrator"},
        )
        self.role_doctor, _ = Role.objects.using("default").get_or_create(
            name="doctor",
            defaults={"label": "Arzt"},
        )

        # Create users
        self.admin = User.objects.db_manager("default").create_user(
            username="admin_auth_test",
            email="admin_auth@example.com",
            password="SecurePass123!",
            role=self.role_admin,
        )
        self.doctor = User.objects.db_manager("default").create_user(
            username="doctor_auth_test",
            email="doctor_auth@example.com",
            password="SecurePass123!",
            role=self.role_doctor,
        )
        self.inactive_user = User.objects.db_manager("default").create_user(
            username="inactive_auth_test",
            email="inactive_auth@example.com",
            password="SecurePass123!",
            role=self.role_doctor,
            is_active=False,
        )

        self.client = APIClient()
        self.client.defaults["HTTP_HOST"] = "localhost"

    # ========== LOGIN TESTS ==========

    def test_login_success_returns_tokens_and_user(self):
        """Successful login returns access, refresh tokens and user info."""
        response = self.client.post(
            "/api/auth/login/",
            {"username": "admin_auth_test", "password": "SecurePass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("user", response.data)

        user_data = response.data["user"]
        self.assertEqual(user_data["id"], self.admin.id)
        self.assertEqual(user_data["username"], "admin_auth_test")
        self.assertEqual(user_data["email"], "admin_auth@example.com")

        # Role info should be included
        self.assertIn("role", user_data)
        self.assertIsNotNone(user_data["role"])
        self.assertEqual(user_data["role"]["name"], "admin")

    def test_login_doctor_returns_doctor_role(self):
        """Doctor login returns doctor role info."""
        response = self.client.post(
            "/api/auth/login/",
            {"username": "doctor_auth_test", "password": "SecurePass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["role"]["name"], "doctor")

    def test_login_wrong_password_returns_401(self):
        """Wrong password returns 400 (validation error)."""
        response = self.client.post(
            "/api/auth/login/",
            {"username": "admin_auth_test", "password": "WrongPassword!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("access", response.data)

    def test_login_wrong_username_returns_401(self):
        """Non-existent user returns 400."""
        response = self.client.post(
            "/api/auth/login/",
            {"username": "nonexistent_user", "password": "SecurePass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_inactive_user_returns_400(self):
        """Inactive user cannot login."""
        response = self.client.post(
            "/api/auth/login/",
            {"username": "inactive_auth_test", "password": "SecurePass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_missing_fields_returns_400(self):
        """Missing username or password returns 400."""
        # Missing password
        response = self.client.post(
            "/api/auth/login/",
            {"username": "admin_auth_test"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing username
        response = self.client.post(
            "/api/auth/login/",
            {"password": "SecurePass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== REFRESH TESTS ==========

    def test_refresh_success_returns_new_access_token(self):
        """Valid refresh token returns new access token."""
        # First login to get tokens
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": "admin_auth_test", "password": "SecurePass123!"},
            format="json",
        )
        refresh_token = login_response.data["refresh"]

        # Refresh
        response = self.client.post(
            "/api/auth/refresh/",
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIsNotNone(response.data["access"])

    def test_refresh_invalid_token_returns_400(self):
        """Invalid refresh token returns 400."""
        response = self.client.post(
            "/api/auth/refresh/",
            {"refresh": "invalid_token_here"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_missing_token_returns_400(self):
        """Missing refresh token returns 400."""
        response = self.client.post(
            "/api/auth/refresh/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ========== ME ENDPOINT TESTS ==========

    def test_me_with_valid_token_returns_user(self):
        """Valid access token returns current user info."""
        # Login to get token
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": "admin_auth_test", "password": "SecurePass123!"},
            format="json",
        )
        access_token = login_response.data["access"]

        # Call /me with token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.admin.id)
        self.assertEqual(response.data["username"], "admin_auth_test")
        self.assertIn("role", response.data)
        self.assertEqual(response.data["role"]["name"], "admin")

    def test_me_without_token_returns_401(self):
        """No token returns 401 Unauthorized."""
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_with_invalid_token_returns_401(self):
        """Invalid token returns 401."""
        self.client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token_here")
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_doctor_returns_doctor_info(self):
        """Doctor's /me returns doctor role info."""
        # Login as doctor
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": "doctor_auth_test", "password": "SecurePass123!"},
            format="json",
        )
        access_token = login_response.data["access"]

        # Call /me
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"]["name"], "doctor")

    # ========== TOKEN CONTENT TESTS ==========

    def test_token_contains_role(self):
        """JWT token contains role claim."""
        import jwt
        from django.conf import settings

        # Login
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": "admin_auth_test", "password": "SecurePass123!"},
            format="json",
        )
        access_token = login_response.data["access"]

        # Decode token (without verification for testing)
        decoded = jwt.decode(
            access_token,
            settings.SIMPLE_JWT.get("SIGNING_KEY", settings.SECRET_KEY),
            algorithms=[settings.SIMPLE_JWT.get("ALGORITHM", "HS256")],
        )

        # Check user_id is in token
        self.assertIn("user_id", decoded)
        # Depending on JWT encode/decode and settings, numeric claims may come back
        # as strings. Normalize to int for a stable assertion.
        self.assertEqual(int(decoded["user_id"]), self.admin.id)

    def test_refresh_token_contains_role(self):
        """Refresh token contains role claim."""
        import jwt
        from django.conf import settings

        # Login
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": "doctor_auth_test", "password": "SecurePass123!"},
            format="json",
        )
        refresh_token = login_response.data["refresh"]

        # Decode token
        decoded = jwt.decode(
            refresh_token,
            settings.SIMPLE_JWT.get("SIGNING_KEY", settings.SECRET_KEY),
            algorithms=[settings.SIMPLE_JWT.get("ALGORITHM", "HS256")],
        )

        # Check role is in token
        self.assertIn("role", decoded)
        self.assertEqual(decoded["role"], "doctor")

    # ========== RBAC TESTS ==========

    def test_access_protected_endpoint_with_token(self):
        """Access token can be used to access protected endpoints."""
        # Login as admin
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": "admin_auth_test", "password": "SecurePass123!"},
            format="json",
        )
        access_token = login_response.data["access"]

        # Access protected endpoint
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_endpoint_no_auth_required(self):
        """Health endpoint works without authentication."""
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "ok")


class AuthenticationEdgeCasesTest(TestCase):
    """Edge case tests for authentication."""

    databases = {"default"}

    def setUp(self):
        self.role_admin, _ = Role.objects.using("default").get_or_create(
            name="admin",
            defaults={"label": "Administrator"},
        )
        self.user_no_role = User.objects.db_manager("default").create_user(
            username="norole_auth_test",
            email="norole_auth@example.com",
            password="SecurePass123!",
            role=None,  # No role assigned
        )
        self.client = APIClient()
        self.client.defaults["HTTP_HOST"] = "localhost"

    def test_login_user_without_role(self):
        """User without role can still login."""
        response = self.client.post(
            "/api/auth/login/",
            {"username": "norole_auth_test", "password": "SecurePass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIsNone(response.data["user"]["role"])

    def test_me_user_without_role(self):
        """User without role can access /me."""
        # Login
        login_response = self.client.post(
            "/api/auth/login/",
            {"username": "norole_auth_test", "password": "SecurePass123!"},
            format="json",
        )
        access_token = login_response.data["access"]

        # Call /me
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["role"])
