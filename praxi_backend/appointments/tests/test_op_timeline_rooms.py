from __future__ import annotations

from datetime import datetime, time

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Operation, OperationType, Resource
from praxi_backend.core.models import AuditLog, Role, User


class OpTimelineRoomsRBACMiniTest(TestCase):
	"""RBAC- und Sichtbarkeitstest für /api/op-timeline/rooms/.

	Szenario:
	- OP 1: OP A (doctor)
	- OP 2: OP B (other doctor)

	Erwartung:
	- admin/assistant/billing: sehen alle Räume und die jeweiligen OPs
	- doctor: GET erlaubt, sieht nur eigene OPs; andere Räume dürfen erscheinen mit operations=[]
	- Audit: jeder GET erzeugt op_timeline_view

	Nur default/system-DB; medical-DB bleibt unberührt.
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
			defaults={"label": "Assistenz"},
		)
		role_billing, _ = Role.objects.using("default").get_or_create(
			name="billing",
			defaults={"label": "Abrechnung"},
		)
		role_doctor, _ = Role.objects.using("default").get_or_create(
			name="doctor",
			defaults={"label": "Arzt"},
		)

		self.admin = User.objects.db_manager("default").create_user(
			username="admin_op_timeline_rooms",
			email="admin_op_timeline_rooms@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.assistant = User.objects.db_manager("default").create_user(
			username="assistant_op_timeline_rooms",
			email="assistant_op_timeline_rooms@example.com",
			password="DummyPass123!",
			role=role_assistant,
		)
		self.billing = User.objects.db_manager("default").create_user(
			username="billing_op_timeline_rooms",
			email="billing_op_timeline_rooms@example.com",
			password="DummyPass123!",
			role=role_billing,
		)
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor_op_timeline_rooms",
			email="doctor_op_timeline_rooms@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="Rooms",
		)
		self.doctor_other = User.objects.db_manager("default").create_user(
			username="doctor_op_timeline_rooms_other",
			email="doctor_op_timeline_rooms_other@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="Other",
		)

		self.room_1 = Resource.objects.using("default").create(name="OP 1", type="room", active=True)
		self.room_2 = Resource.objects.using("default").create(name="OP 2", type="room", active=True)
		self.op_type = OperationType.objects.using("default").create(
			name="Rooms-OP",
			prep_duration=0,
			op_duration=60,
			post_duration=0,
			active=True,
		)

		self.day = datetime(2030, 1, 7).date()  # Monday
		self.tz = timezone.get_current_timezone()

		self.op_a = Operation.objects.using("default").create(
			patient_id=1,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.room_1,
			op_type=self.op_type,
			start_time=timezone.make_aware(datetime.combine(self.day, time(10, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(11, 0)), self.tz),
			status="planned",
			notes="A",
		)
		self.op_b = Operation.objects.using("default").create(
			patient_id=2,
			primary_surgeon=self.doctor_other,
			assistant=None,
			anesthesist=None,
			op_room=self.room_2,
			op_type=self.op_type,
			start_time=timezone.make_aware(datetime.combine(self.day, time(12, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(13, 0)), self.tz),
			status="planned",
			notes="B",
		)

	def _assert_audit_increment(self, before_count: int):
		self.assertEqual(AuditLog.objects.using("default").count(), before_count + 1)
		last = AuditLog.objects.using("default").order_by("-id").first()
		self.assertIsNotNone(last)
		self.assertEqual(last.action, "op_timeline_view")

	def test_rooms_endpoint_rbac_and_visibility(self):
		date_q = {"date": self.day.isoformat()}

		def _group_map(data):
			# Multiple rooms may exist in keepdb; index by room id.
			return {int(g["room"]["id"]): g for g in (data or [])}

		# 1) admin
		admin_client = self._client_for(self.admin)
		before = AuditLog.objects.using("default").count()
		r_admin = admin_client.get("/api/op-timeline/rooms/", date_q)
		self.assertEqual(r_admin.status_code, 200)
		self._assert_audit_increment(before)
		m_admin = _group_map(r_admin.data)
		self.assertIn(self.room_1.id, m_admin)
		self.assertIn(self.room_2.id, m_admin)
		self.assertEqual([o["id"] for o in m_admin[self.room_1.id]["operations"]], [self.op_a.id])
		self.assertEqual([o["id"] for o in m_admin[self.room_2.id]["operations"]], [self.op_b.id])

		# 2) assistant
		assistant_client = self._client_for(self.assistant)
		before = AuditLog.objects.using("default").count()
		r_assistant = assistant_client.get("/api/op-timeline/rooms/", date_q)
		self.assertEqual(r_assistant.status_code, 200)
		self._assert_audit_increment(before)
		m_assistant = _group_map(r_assistant.data)
		self.assertIn(self.room_1.id, m_assistant)
		self.assertIn(self.room_2.id, m_assistant)

		# 3) billing
		billing_client = self._client_for(self.billing)
		before = AuditLog.objects.using("default").count()
		r_billing = billing_client.get("/api/op-timeline/rooms/", date_q)
		self.assertEqual(r_billing.status_code, 200)
		self._assert_audit_increment(before)
		m_billing = _group_map(r_billing.data)
		self.assertIn(self.room_1.id, m_billing)
		self.assertIn(self.room_2.id, m_billing)

		# 4) doctor
		doctor_client = self._client_for(self.doctor)
		before = AuditLog.objects.using("default").count()
		r_doctor = doctor_client.get("/api/op-timeline/rooms/", date_q)
		self.assertEqual(r_doctor.status_code, 200)
		self._assert_audit_increment(before)
		m_doctor = _group_map(r_doctor.data)
		self.assertIn(self.room_1.id, m_doctor)
		self.assertIn(self.room_2.id, m_doctor)
		# Only own OP in OP 1
		self.assertEqual([o["id"] for o in m_doctor[self.room_1.id]["operations"]], [self.op_a.id])
		# OP 2 appears but operations empty
		self.assertEqual(m_doctor[self.room_2.id]["operations"], [])
