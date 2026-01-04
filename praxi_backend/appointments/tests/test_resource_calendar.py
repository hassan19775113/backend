from __future__ import annotations

from datetime import datetime, time

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Appointment, AppointmentResource, AppointmentType, Operation, OperationType, Resource
from praxi_backend.core.models import AuditLog, Role, User


class ResourceCalendarMiniTest(TestCase):
	"""Mini-Test: Ressourcen-Kalender (Outlook Room View).

	Szenario:
	- Resource A: Termin 10:00–10:30 (doctor)
	- Resource A: OP 11:00–12:00 (doctor)
	- Resource B: OP 09:00–10:00 (other doctor)

	Erwartung:
	- GET /api/resource-calendar/?date=...&resource_ids=A,B
	  -> A: [appointment, operation]
	  -> B: [operation]
	- doctor sieht nur eigene Buchungen (B leer)
	- Audit wird geschrieben (resource_calendar_view)

	Nur default/system-DB; medical DB bleibt unberührt.
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
		role_doctor, _ = Role.objects.using("default").get_or_create(
			name="doctor",
			defaults={"label": "Arzt"},
		)

		self.admin = User.objects.db_manager("default").create_user(
			username="admin_resource_calendar",
			email="admin_resource_calendar@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor_resource_calendar",
			email="doctor_resource_calendar@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="RC",
		)
		self.doctor_other = User.objects.db_manager("default").create_user(
			username="doctor_resource_calendar_other",
			email="doctor_resource_calendar_other@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="Other",
		)

		self.res_a = Resource.objects.using("default").create(name="OP 1", type="room", active=True)
		self.res_b = Resource.objects.using("default").create(name="OP 2", type="room", active=True)

		self.appt_type = AppointmentType.objects.using("default").create(
			name="Sprechstunde",
			color="#ABCDEF",
			active=True,
		)
		self.op_type = OperationType.objects.using("default").create(
			name="RC-OP",
			prep_duration=0,
			op_duration=60,
			post_duration=0,
			active=True,
		)

		self.day = datetime(2030, 1, 7).date()  # Monday
		self.tz = timezone.get_current_timezone()

		appt = Appointment.objects.using("default").create(
			patient_id=1,
			type=self.appt_type,
			doctor=self.doctor,
			start_time=timezone.make_aware(datetime.combine(self.day, time(10, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(10, 30)), self.tz),
			status="scheduled",
			notes="Termin",
		)
		AppointmentResource.objects.using("default").create(appointment=appt, resource=self.res_a)

		self.op_a = Operation.objects.using("default").create(
			patient_id=2,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.res_a,
			op_type=self.op_type,
			start_time=timezone.make_aware(datetime.combine(self.day, time(11, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(12, 0)), self.tz),
			status="planned",
			notes="OP_A",
		)
		self.op_b = Operation.objects.using("default").create(
			patient_id=3,
			primary_surgeon=self.doctor_other,
			assistant=None,
			anesthesist=None,
			op_room=self.res_b,
			op_type=self.op_type,
			start_time=timezone.make_aware(datetime.combine(self.day, time(9, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(10, 0)), self.tz),
			status="planned",
			notes="OP_B",
		)

	def test_resource_calendar_grouping_rbac_and_audit(self):
		admin_client = self._client_for(self.admin)
		doctor_client = self._client_for(self.doctor)

		# admin
		before = AuditLog.objects.using("default").count()
		r = admin_client.get(
			"/api/resource-calendar/",
			{"date": self.day.isoformat(), "resource_ids": f"{self.res_a.id},{self.res_b.id}"},
		)
		self.assertEqual(r.status_code, 200)
		self.assertEqual(AuditLog.objects.using("default").count(), before + 1)
		last = AuditLog.objects.using("default").order_by("-id").first()
		self.assertIsNotNone(last)
		self.assertEqual(last.action, "resource_calendar_view")

		# Two columns in the requested order
		self.assertEqual([c["resource"]["id"] for c in r.data], [self.res_a.id, self.res_b.id])
		col_a = r.data[0]
		col_b = r.data[1]

		self.assertEqual([b["kind"] for b in col_a["bookings"]][:2], ["appointment", "operation"])
		self.assertEqual([b["kind"] for b in col_b["bookings"]][:1], ["operation"])

		# doctor: only own bookings (res_b empty)
		before = AuditLog.objects.using("default").count()
		r_doc = doctor_client.get(
			"/api/resource-calendar/",
			{"date": self.day.isoformat(), "resource_ids": f"{self.res_a.id},{self.res_b.id}"},
		)
		self.assertEqual(r_doc.status_code, 200)
		self.assertEqual(AuditLog.objects.using("default").count(), before + 1)

		self.assertEqual([c["resource"]["id"] for c in r_doc.data], [self.res_a.id, self.res_b.id])
		col_a_d = r_doc.data[0]
		col_b_d = r_doc.data[1]
		kinds_a = [b["kind"] for b in col_a_d["bookings"]]
		self.assertIn("appointment", kinds_a)
		self.assertIn("operation", kinds_a)
		self.assertEqual(col_b_d["bookings"], [])
