from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import AppointmentType, DoctorHours, PracticeHours
from praxi_backend.core.models import Role, User


class AppointmentSuggestRBACTest(TestCase):
	"""RBAC-Tests für /api/appointments/suggest/.

	Läuft ausschließlich gegen die system Test-DB (default) und berührt medical nicht.
	"""

	databases = {"default"}

	def _client_for(self, user: User) -> APIClient:
		client = APIClient()
		client.defaults["HTTP_HOST"] = "localhost"
		client.force_authenticate(user=user)
		return client

	def setUp(self):
		role_admin, _ = Role.objects.using("default").get_or_create(
			name="admin",
			defaults={"label": "Administrator"},
		)
		role_assistant, _ = Role.objects.using("default").get_or_create(
			name="assistant",
			defaults={"label": "MFA"},
		)
		role_doctor, _ = Role.objects.using("default").get_or_create(
			name="doctor",
			defaults={"label": "Arzt"},
		)
		role_billing, _ = Role.objects.using("default").get_or_create(
			name="billing",
			defaults={"label": "Abrechnung"},
		)

		self.admin = User.objects.db_manager("default").create_user(
			username="admin_test",
			email="admin_test@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.assistant = User.objects.db_manager("default").create_user(
			username="assistant_test",
			email="assistant_test@example.com",
			password="DummyPass123!",
			role=role_assistant,
		)
		self.doctor1 = User.objects.db_manager("default").create_user(
			username="doctor1_test",
			email="doctor1_test@example.com",
			password="DummyPass123!",
			role=role_doctor,
		)
		self.doctor2 = User.objects.db_manager("default").create_user(
			username="doctor2_test",
			email="doctor2_test@example.com",
			password="DummyPass123!",
			role=role_doctor,
		)
		self.billing = User.objects.db_manager("default").create_user(
			username="billing_test",
			email="billing_test@example.com",
			password="DummyPass123!",
			role=role_billing,
		)

		# Ensure suggestions can be generated quickly (next Monday).
		base = timezone.localdate() + timedelta(days=1)
		self.monday = base - timedelta(days=base.weekday())

		PracticeHours.objects.using("default").create(
			weekday=0,
			start_time="08:00:00",
			end_time="16:00:00",
			active=True,
		)
		DoctorHours.objects.using("default").create(
			doctor=self.doctor2,
			weekday=0,
			start_time="09:00:00",
			end_time="12:00:00",
			active=True,
		)
		self.appt_type = AppointmentType.objects.using("default").create(
			name="RBAC-Typ",
			duration_minutes=30,
			active=True,
		)

	def test_doctor_cannot_request_other_doctor(self):
		client = self._client_for(self.doctor1)
		r = client.get(
			"/api/appointments/suggest/",
			{
				"doctor_id": self.doctor2.id,
				"type_id": self.appt_type.id,
				"start_date": self.monday.isoformat(),
				"limit": 1,
			},
		)
		self.assertEqual(r.status_code, 403)

	def test_admin_and_assistant_can_request_other_doctor(self):
		admin_client = self._client_for(self.admin)
		assistant_client = self._client_for(self.assistant)

		r_admin = admin_client.get(
			"/api/appointments/suggest/",
			{
				"doctor_id": self.doctor2.id,
				"type_id": self.appt_type.id,
				"start_date": self.monday.isoformat(),
				"limit": 1,
			},
		)
		self.assertEqual(r_admin.status_code, 200)

		r_assistant = assistant_client.get(
			"/api/appointments/suggest/",
			{
				"doctor_id": self.doctor2.id,
				"type_id": self.appt_type.id,
				"start_date": self.monday.isoformat(),
				"limit": 1,
			},
		)
		self.assertEqual(r_assistant.status_code, 200)

	def test_billing_cannot_request_other_doctor(self):
		client = self._client_for(self.billing)
		r = client.get(
			"/api/appointments/suggest/",
			{
				"doctor_id": self.doctor2.id,
				"type_id": self.appt_type.id,
				"start_date": self.monday.isoformat(),
				"limit": 1,
			},
		)
		self.assertEqual(r.status_code, 200)
