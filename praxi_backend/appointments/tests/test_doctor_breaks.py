from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework import serializers
from rest_framework.test import APIClient

from praxi_backend.appointments.models import Appointment, AppointmentType, DoctorBreak, DoctorHours, PracticeHours
from praxi_backend.appointments.serializers import AppointmentCreateUpdateSerializer
from praxi_backend.core.models import Role, User


class DoctorBreaksMiniTest(TestCase):
	"""Mini-Test für Pausen/Blockzeiten.

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

		# Pick a deterministic Monday.
		base = timezone.localdate() + timedelta(days=1)
		self.monday = base - timedelta(days=base.weekday())

		# Working hours Mon 09:00-17:00 (practice + doctor)
		PracticeHours.objects.using("default").create(
			weekday=0,
			start_time="09:00:00",
			end_time="17:00:00",
			active=True,
		)
		DoctorHours.objects.using("default").create(
			doctor=self.doctor,
			weekday=0,
			start_time="09:00:00",
			end_time="17:00:00",
			active=True,
		)

		self.appt_type = AppointmentType.objects.using("default").create(
			name="Sprechstunde",
			duration_minutes=30,
			active=True,
		)

		# Breaks
		DoctorBreak.objects.using("default").create(
			doctor=None,
			date=self.monday,
			start_time="12:00:00",
			end_time="13:00:00",
			reason="Mittagspause",
			active=True,
		)
		DoctorBreak.objects.using("default").create(
			doctor=self.doctor,
			date=self.monday,
			start_time="15:00:00",
			end_time="16:00:00",
			reason="Blockzeit",
			active=True,
		)

	def _dt(self, hour: int, minute: int = 0):
		tz = timezone.get_current_timezone()
		return timezone.make_aware(
			timezone.datetime(self.monday.year, self.monday.month, self.monday.day, hour, minute, 0),
			tz,
		)

	def test_appointment_validation_blocks_breaks(self):
		serializer = AppointmentCreateUpdateSerializer()

		with self.assertRaises(serializers.ValidationError) as ctx1:
			serializer.validate(
				{
					"patient_id": 1,
					"type": self.appt_type,
					"doctor": self.doctor,
					"start_time": self._dt(12, 30),
					"end_time": self._dt(13, 0),
					"status": "scheduled",
				}
			)
		self.assertIn("Doctor unavailable.", str(ctx1.exception.detail))

		with self.assertRaises(serializers.ValidationError) as ctx2:
			serializer.validate(
				{
					"patient_id": 1,
					"type": self.appt_type,
					"doctor": self.doctor,
					"start_time": self._dt(15, 30),
					"end_time": self._dt(16, 0),
					"status": "scheduled",
				}
			)
		self.assertIn("Doctor unavailable.", str(ctx2.exception.detail))

	def test_suggest_skips_breaks_and_returns_1400_1430(self):
		# Make suggestion deterministic by blocking all morning slots and 13:00-14:00.
		Appointment.objects.using("default").create(
			patient_id=1,
			type=self.appt_type,
			doctor=self.doctor,
			start_time=self._dt(9, 0),
			end_time=self._dt(12, 0),
			status="scheduled",
			notes="BLOCK_MORNING",
		)
		Appointment.objects.using("default").create(
			patient_id=2,
			type=self.appt_type,
			doctor=self.doctor,
			start_time=self._dt(13, 0),
			end_time=self._dt(14, 0),
			status="scheduled",
			notes="BLOCK_13_14",
		)

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
		self.assertEqual(len(r.data.get("primary_suggestions", [])), 1)

		s = r.data["primary_suggestions"][0]
		self.assertTrue("T14:00:00" in s["start_time"])
		self.assertTrue("T14:30:00" in s["end_time"])
