from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Appointment, AppointmentType, DoctorHours, PracticeHours
from praxi_backend.core.models import AuditLog, Role, User


class AppointmentSuggestMiniTest(TestCase):
	"""Mini-Test für /api/appointments/suggest/.

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

		# Pick a deterministic Monday in the near future.
		base = timezone.localdate() + timedelta(days=1)
		self.monday = base - timedelta(days=base.weekday())

		# Working hours: Practice Mon 08:00-16:00, Doctor Mon 09:00-12:00
		PracticeHours.objects.using("default").create(
			weekday=0,
			start_time="08:00:00",
			end_time="16:00:00",
			active=True,
		)
		DoctorHours.objects.using("default").create(
			doctor=self.doctor,
			weekday=0,
			start_time="09:00:00",
			end_time="12:00:00",
			active=True,
		)

		self.appt_type = AppointmentType.objects.using("default").create(
			name="Kontrolle",
			duration_minutes=30,
			active=True,
		)

		# Existing appointment: 09:00-09:30 on Monday
		tz = timezone.get_current_timezone()
		start1 = timezone.make_aware(
			timezone.datetime(self.monday.year, self.monday.month, self.monday.day, 9, 0, 0),
			tz,
		)
		end1 = start1 + timedelta(minutes=30)
		Appointment.objects.using("default").create(
			patient_id=1,
			type=self.appt_type,
			doctor=self.doctor,
			start_time=start1,
			end_time=end1,
			status="scheduled",
			notes="SUGGEST_BLOCK",
		)

	def test_suggest_returns_0930_1000(self):
		before = AuditLog.objects.using("default").count()

		r = self.client.get(
			"/api/appointments/suggest/",
			{
				"doctor_id": self.doctor.id,
				"type_id": self.appt_type.id,
				"start_date": self.monday.isoformat(),
				"limit": 1,
			},
		)
		self.assertEqual(r.status_code, 200)
		self.assertIn("primary_doctor", r.data)
		self.assertIn("primary_suggestions", r.data)
		self.assertEqual(r.data["primary_doctor"]["id"], self.doctor.id)
		self.assertEqual(len(r.data["primary_suggestions"]), 1)

		s = r.data["primary_suggestions"][0]
		self.assertEqual(s["type"]["id"], self.appt_type.id)

		self.assertTrue(s["start_time"].endswith("09:30:00") or "T09:30:00" in s["start_time"])
		self.assertTrue(s["end_time"].endswith("10:00:00") or "T10:00:00" in s["end_time"])

		after = AuditLog.objects.using("default").count()
		self.assertEqual(after, before + 1)
		last = AuditLog.objects.using("default").order_by("-id").first()
		self.assertIsNotNone(last)
		self.assertEqual(last.action, "appointment_suggest")
		self.assertEqual(last.user_id, self.admin.id)
