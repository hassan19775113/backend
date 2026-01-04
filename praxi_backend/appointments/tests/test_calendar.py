from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Appointment
from praxi_backend.core.models import Role, User


class CalendarViewsMiniTest(TestCase):
	"""Mini-Test für Calendar Day/Week/Month.

	Läuft ausschließlich gegen die system Test-DB (default) und berührt medical nicht.
	"""

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
			username="admin_test",
			email="admin_test@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor1",
			email="doctor1@example.com",
			password="DummyPass123!",
			role=role_doctor,
		)

		self.client = APIClient()
		self.client.defaults["HTTP_HOST"] = "localhost"
		self.client.force_authenticate(user=self.admin)

		base = timezone.now() + timedelta(days=5)
		self.day = base.date()

		start1 = timezone.make_aware(
			timezone.datetime(self.day.year, self.day.month, self.day.day, 9, 0, 0),
			timezone.get_current_timezone(),
		)
		end1 = start1 + timedelta(minutes=30)

		start2 = timezone.make_aware(
			timezone.datetime(self.day.year, self.day.month, self.day.day, 10, 0, 0),
			timezone.get_current_timezone(),
		)
		end2 = start2 + timedelta(minutes=30)

		Appointment.objects.using("default").create(
			patient_id=1,
			doctor=self.doctor,
			start_time=start1,
			end_time=end1,
			status="scheduled",
			notes="CAL_TEST_1",
		)
		Appointment.objects.using("default").create(
			patient_id=2,
			doctor=self.doctor,
			start_time=start2,
			end_time=end2,
			status="scheduled",
			notes="CAL_TEST_2",
		)

	def _count(self, resp):
		data = resp.data or {}
		return len(data.get("appointments", []))

	def test_day_week_month_return_two_appointments(self):
		date_str = self.day.isoformat()

		r_day = self.client.get(f"/api/calendar/day/?date={date_str}")
		self.assertEqual(r_day.status_code, 200)
		self.assertGreaterEqual(self._count(r_day), 2)

		r_week = self.client.get(f"/api/calendar/week/?date={date_str}")
		self.assertEqual(r_week.status_code, 200)
		self.assertGreaterEqual(self._count(r_week), 2)

		r_month = self.client.get(f"/api/calendar/month/?date={date_str}")
		self.assertEqual(r_month.status_code, 200)
		self.assertGreaterEqual(self._count(r_month), 2)
