from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import DoctorAbsence, DoctorHours, PracticeHours
from praxi_backend.core.models import AuditLog, Role, User


class DoctorSubstitutionSuggestMiniTest(TestCase):
	"""Mini-Test:
	- Dr. A abwesend
	- Dr. B verfügbar
	- Suggest für Dr. A liefert fallback Slot von Dr. B

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
			username="admin_sub_test",
			email="admin_sub_test@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.doctor_a = User.objects.db_manager("default").create_user(
			username="doctor_a",
			email="doctor_a@example.com",
			password="DummyPass123!",
			role=role_doctor,
		)
		self.doctor_b = User.objects.db_manager("default").create_user(
			username="doctor_b",
			email="doctor_b@example.com",
			password="DummyPass123!",
			role=role_doctor,
		)

		self.client = APIClient()
		self.client.defaults["HTTP_HOST"] = "localhost"
		self.client.force_authenticate(user=self.admin)

		# Pick a deterministic Monday in the near future.
		base = timezone.localdate() + timedelta(days=1)
		self.monday = base - timedelta(days=base.weekday())

		# Working hours Mon 09:00-17:00 (practice + both doctors)
		PracticeHours.objects.using("default").create(
			weekday=0,
			start_time="09:00:00",
			end_time="17:00:00",
			active=True,
		)
		for d in (self.doctor_a, self.doctor_b):
			DoctorHours.objects.using("default").create(
				doctor=d,
				weekday=0,
				start_time="09:00:00",
				end_time="17:00:00",
				active=True,
			)

		# Dr. A absent on that Monday
		DoctorAbsence.objects.using("default").create(
			doctor=self.doctor_a,
			start_date=self.monday,
			end_date=self.monday,
			reason="Urlaub",
			active=True,
		)

	def test_suggest_falls_back_to_other_doctor(self):
		before = list(AuditLog.objects.using("default").values_list("action", flat=True))

		r = self.client.get(
			"/api/appointments/suggest/",
			{
				"doctor_id": self.doctor_a.id,
				"duration_minutes": 30,
				"start_date": self.monday.isoformat(),
				"limit": 1,
			},
		)

		self.assertEqual(r.status_code, 200)
		self.assertEqual(r.data["primary_doctor"]["id"], self.doctor_a.id)
		self.assertEqual(r.data.get("primary_suggestions"), [])

		fallback = r.data.get("fallback_suggestions") or []
		self.assertGreaterEqual(len(fallback), 1)
		self.assertEqual(fallback[0]["doctor"]["id"], self.doctor_b.id)
		self.assertGreaterEqual(len(fallback[0].get("suggestions") or []), 1)

		slot = fallback[0]["suggestions"][0]
		self.assertIn("T09:00:00", slot["start_time"])
		self.assertIn("T09:30:00", slot["end_time"])

		actions = list(AuditLog.objects.using("default").values_list("action", flat=True))
		new_actions = actions[len(before) :]
		self.assertIn("appointment_suggest", new_actions)
		self.assertIn("doctor_substitution_suggest", new_actions)
