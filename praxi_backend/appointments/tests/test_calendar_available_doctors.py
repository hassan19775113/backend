from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Appointment, DoctorAbsence, DoctorBreak, DoctorHours, PracticeHours
from praxi_backend.core.models import AuditLog, Role, User


class CalendarAvailableDoctorsMiniTest(TestCase):
	"""Mini-Test: Calendar-Day liefert available_doctors + reason.

	Vorgabe-Szenario (2025-01-10, Freitag):
	- Dr. A: Abwesend
	- Dr. B: Pause (blockt komplett seine Stunden)
	- Dr. C: Keine Arbeitszeiten
	- Dr. D: Hat einen Termin (blockt komplett seine Stunden)
	- Dr. E: Voll verfügbar

	Wichtig: Nur default/system-DB. medical bleibt unberührt.
	"""

	databases = {"default"}

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

		self.admin = User.objects.db_manager("default").create_user(
			username="admin_cal_avail",
			email="admin_cal_avail@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.assistant = User.objects.db_manager("default").create_user(
			username="assistant_cal_avail",
			email="assistant_cal_avail@example.com",
			password="DummyPass123!",
			role=role_assistant,
		)

		# Create doctors A..E in deterministic order (id ascending).
		self.dr_a = User.objects.db_manager("default").create_user(
			username="dr_a",
			email="dr_a@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="A",
		)
		self.dr_b = User.objects.db_manager("default").create_user(
			username="dr_b",
			email="dr_b@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="B",
		)
		self.dr_c = User.objects.db_manager("default").create_user(
			username="dr_c",
			email="dr_c@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="C",
		)
		self.dr_d = User.objects.db_manager("default").create_user(
			username="dr_d",
			email="dr_d@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="D",
		)
		self.dr_e = User.objects.db_manager("default").create_user(
			username="dr_e",
			email="dr_e@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="E",
		)

		self.client_admin = APIClient()
		self.client_admin.defaults["HTTP_HOST"] = "localhost"
		self.client_admin.force_authenticate(user=self.admin)

		self.client_assistant = APIClient()
		self.client_assistant.defaults["HTTP_HOST"] = "localhost"
		self.client_assistant.force_authenticate(user=self.assistant)

		self.day = date(2025, 1, 10)  # Friday
		weekday = self.day.weekday()
		self.assertEqual(weekday, 4)  # 0=Mon .. 4=Fri

		# Practice hours on Friday ensure hours exist in general.
		PracticeHours.objects.using("default").create(
			weekday=weekday,
			start_time=time(9, 0),
			end_time=time(17, 0),
			active=True,
		)

		# Dr. A: has hours but absent that day.
		DoctorHours.objects.using("default").create(
			doctor=self.dr_a,
			weekday=weekday,
			start_time=time(9, 0),
			end_time=time(17, 0),
			active=True,
		)
		DoctorAbsence.objects.using("default").create(
			doctor=self.dr_a,
			start_date=self.day,
			end_date=self.day,
			reason="Urlaub",
			active=True,
		)

		# Dr. B: only works 12:00-13:00 and has a break 12:00-13:00 => fully blocked by break.
		DoctorHours.objects.using("default").create(
			doctor=self.dr_b,
			weekday=weekday,
			start_time=time(12, 0),
			end_time=time(13, 0),
			active=True,
		)
		DoctorBreak.objects.using("default").create(
			doctor=self.dr_b,
			date=self.day,
			start_time=time(12, 0),
			end_time=time(13, 0),
			reason="Pause",
			active=True,
		)

		# Dr. C: no DoctorHours on Friday => no_hours

		# Dr. D: only works 10:00-10:30 and already booked => busy.
		DoctorHours.objects.using("default").create(
			doctor=self.dr_d,
			weekday=weekday,
			start_time=time(10, 0),
			end_time=time(10, 30),
			active=True,
		)
		tz = timezone.get_current_timezone()
		start_d = timezone.make_aware(datetime.combine(self.day, time(10, 0)), tz)
		end_d = start_d + timedelta(minutes=30)
		Appointment.objects.using("default").create(
			patient_id=1,
			doctor=self.dr_d,
			start_time=start_d,
			end_time=end_d,
			status="scheduled",
			notes="BUSY_BLOCK",
		)

		# Dr. E: full availability 09:00-17:00.
		DoctorHours.objects.using("default").create(
			doctor=self.dr_e,
			weekday=weekday,
			start_time=time(9, 0),
			end_time=time(17, 0),
			active=True,
		)

	def test_calendar_day_available_doctors_and_audit_and_rbac(self):
		before = AuditLog.objects.using("default").count()

		# RBAC: admin can access
		r = self.client_admin.get(f"/api/calendar/day/?date={self.day.isoformat()}")
		self.assertEqual(r.status_code, 200)

		avail = (r.data or {}).get("available_doctors")
		self.assertIsInstance(avail, list)
		self.assertEqual(len(avail), 5)

		# The view orders doctors by id; we created A..E in order.
		self.assertEqual(avail[0]["id"], self.dr_a.id)
		self.assertEqual(avail[0]["available"], False)
		self.assertEqual(avail[0]["reason"], "absence")

		self.assertEqual(avail[1]["id"], self.dr_b.id)
		self.assertEqual(avail[1]["available"], False)
		self.assertEqual(avail[1]["reason"], "break")

		self.assertEqual(avail[2]["id"], self.dr_c.id)
		self.assertEqual(avail[2]["available"], False)
		self.assertEqual(avail[2]["reason"], "no_hours")

		self.assertEqual(avail[3]["id"], self.dr_d.id)
		self.assertEqual(avail[3]["available"], False)
		self.assertEqual(avail[3]["reason"], "busy")

		self.assertEqual(avail[4]["id"], self.dr_e.id)
		self.assertEqual(avail[4]["available"], True)
		self.assertIsNone(avail[4]["reason"])

		after = AuditLog.objects.using("default").count()
		self.assertEqual(after, before + 2)
		last_actions = list(AuditLog.objects.using("default").order_by("-id").values_list("action", flat=True)[:2])
		self.assertIn("doctor_substitution_list", last_actions)

		# RBAC: assistant can access
		r2 = self.client_assistant.get(f"/api/calendar/day/?date={self.day.isoformat()}")
		self.assertEqual(r2.status_code, 200)
