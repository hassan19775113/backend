from __future__ import annotations

from django.test import RequestFactory, TestCase
from praxi_backend.core.models import Role, User
from praxi_backend.dashboard.doctor_views import DoctorDashboardView


class DoctorsDashboardRenderTest(TestCase):
    """Regression tests for the Ärzte dashboard.

    The page previously rendered as "empty" because the view provided context keys
    that did not match the template (`doctors.html`) expectations.
    """

    databases = {"default"}

    def setUp(self):
        role_doctor, _ = Role.objects.using("default").get_or_create(
            name="doctor",
            defaults={"label": "Arzt"},
        )
        self.staff_user = User.objects.db_manager("default").create_user(
            username="test_staff_doctors_dashboard",
            email="test_staff_doctors_dashboard@example.com",
            password="DummyPass123!",
            is_staff=True,
            is_active=True,
        )
        self.doctor = User.objects.db_manager("default").create_user(
            username="test_doctor_dashboard",
            email="test_doctor_dashboard@example.com",
            password="DummyPass123!",
            role=role_doctor,
            first_name="Dr",
            last_name="Dashboard",
            is_active=True,
        )
        self.rf = RequestFactory()

    def test_overview_renders_doctors_table(self):
        request = self.rf.get("/dashboard/doctors/")
        request.user = self.staff_user
        response = DoctorDashboardView.as_view()(request)
        response.render()
        html = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Keine Ärzte konfiguriert", html)

    def test_detail_renders_profile(self):
        request = self.rf.get(
            "/dashboard/doctors/", {"doctor_id": str(self.doctor.id), "period": "week"}
        )
        request.user = self.staff_user
        response = DoctorDashboardView.as_view()(request)
        response.render()
        html = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Arbeitszeiten", html)
        self.assertNotIn("Keine Ärzte konfiguriert", html)
