from __future__ import annotations

from django.test import TestCase

from praxi_backend.core.models import Role, User


class AppointmentsCalendarViewsTest(TestCase):
    """Smoke tests for the staff-only HTML calendar pages.

    These pages are rendered server-side (no JS) and protected by
    `staff_member_required`.
    """

    databases = {"default"}

    def setUp(self):
        role_admin, _ = Role.objects.using("default").get_or_create(
            name="admin",
            defaults={"label": "Administrator"},
        )
        self.staff = User.objects.db_manager("default").create_user(
            username="staff_calendar",
            email="staff_calendar@example.com",
            password="DummyPass123!",
            role=role_admin,
            is_staff=True,
            is_active=True,
        )
        self.client.force_login(self.staff)

    def test_day_calendar_renders(self):
        r = self.client.get("/praxiadmin/dashboard/appointments/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode("utf-8")
        self.assertIn("Termine am", html)
        self.assertIn("Kalenderansicht", html)

    def test_week_calendar_renders(self):
        r = self.client.get("/praxiadmin/dashboard/appointments/week/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode("utf-8")
        self.assertIn("Termine · Woche", html)

    def test_month_calendar_renders(self):
        r = self.client.get("/praxiadmin/dashboard/appointments/month/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode("utf-8")
        self.assertIn("Termine · Monat", html)
