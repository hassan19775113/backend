from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import DoctorHours, PracticeHours
from praxi_backend.core.models import Role, User


class AppointmentSuggestTodayMiniTest(TestCase):
	"""Mini-Test: start_date == heute => keine Vorschläge vor now().

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

	def test_today_starts_at_now_1500(self):
		tz = timezone.get_current_timezone()
		fixed_now = timezone.make_aware(datetime(2030, 1, 15, 15, 0, 0), tz)
		weekday = fixed_now.date().weekday()

		# Arbeitszeit 09:00-17:00 (Praxis und Arzt) am heutigen Wochentag
		PracticeHours.objects.using("default").create(
			weekday=weekday,
			start_time="09:00:00",
			end_time="17:00:00",
			active=True,
		)
		DoctorHours.objects.using("default").create(
			doctor=self.doctor,
			weekday=weekday,
			start_time="09:00:00",
			end_time="17:00:00",
			active=True,
		)

		with patch("django.utils.timezone.now", return_value=fixed_now):
			r = self.client.get(
				"/api/appointments/suggest/",
				{
					"doctor_id": self.doctor.id,
					"duration_minutes": 30,
					"start_date": fixed_now.date().isoformat(),
					"limit": 1,
				},
			)

		self.assertEqual(r.status_code, 200)
		self.assertEqual(len(r.data.get("primary_suggestions", [])), 1)
		s = r.data["primary_suggestions"][0]
		self.assertIn("T15:00:00", s["start_time"])
		self.assertIn("T15:30:00", s["end_time"])
