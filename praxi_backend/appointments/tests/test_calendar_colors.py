from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Appointment, AppointmentType
from praxi_backend.core.models import Role, User


class CalendarColorsMiniTest(TestCase):
	"""Mini-Test: Calendar-Day liefert appointment_color + doctor_color."""

	databases = {"default"}

	def setUp(self):
		role_admin, _ = Role.objects.using("default").get_or_create(
			name="admin",
			defaults={"label": "Administrator"},
		)
		role_doctor, _ = Role.objects.using("default").get_or_create(
			name="doctor",
			defaults={"label": "Arzt"},
		)

		self.admin = User.objects.db_manager("default").create_user(
			username="admin_cal_colors",
			email="admin_cal_colors@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor_cal_colors",
			email="doctor_cal_colors@example.com",
			password="DummyPass123!",
			role=role_doctor,
			calendar_color="#123456",
		)

		self.appt_type = AppointmentType.objects.using("default").create(
			name="Kontrolle",
			duration_minutes=30,
			active=True,
			color="#ABCDEF",
		)

		self.client = APIClient()
		self.client.defaults["HTTP_HOST"] = "localhost"
		self.client.force_authenticate(user=self.admin)

		base = timezone.now() + timedelta(days=5)
		self.day = base.date()
		tz = timezone.get_current_timezone()
		start = timezone.make_aware(
			timezone.datetime(self.day.year, self.day.month, self.day.day, 9, 0, 0),
			tz,
		)
		end = start + timedelta(minutes=30)

		Appointment.objects.using("default").create(
			patient_id=1,
			type=self.appt_type,
			doctor=self.doctor,
			start_time=start,
			end_time=end,
			status="scheduled",
			notes="CAL_COLOR_TEST",
		)

	def test_calendar_day_includes_colors(self):
		r = self.client.get(f"/api/calendar/day/?date={self.day.isoformat()}")
		self.assertEqual(r.status_code, 200)

		appts = (r.data or {}).get("appointments") or []
		self.assertGreaterEqual(len(appts), 1)

		match = next((a for a in appts if a.get("notes") == "CAL_COLOR_TEST"), None)
		self.assertIsNotNone(match)
		self.assertEqual(match.get("appointment_color"), "#ABCDEF")
		self.assertEqual(match.get("doctor_color"), "#123456")
