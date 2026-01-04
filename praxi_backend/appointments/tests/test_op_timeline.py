from __future__ import annotations

from datetime import datetime, time
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Operation, OperationType, Resource
from praxi_backend.core.models import AuditLog, Role, User


class OpTimelineMiniTest(TestCase):
	"""Mini-Test: OP-Timeline.

	Szenario:
	- OP-1: Operation A 10:00–11:00
	- OP-1: Operation B 12:00–13:00
	- OP-2: Operation C 09:00–10:00
	
	Erwartung:
	- Timeline gruppiert korrekt (OP-1 → [A, B], OP-2 → [C]) und je Raum nach start_time sortiert
	- Live liefert nur running/confirmed mit start_time >= now-30min
	- RBAC: doctor sieht nur eigene OPs

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
		role_billing, _ = Role.objects.using("default").get_or_create(
			name="billing",
			defaults={"label": "Abrechnung"},
		)

		self.admin = User.objects.db_manager("default").create_user(
			username="admin_op_timeline",
			email="admin_op_timeline@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor_op_timeline",
			email="doctor_op_timeline@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="Timeline",
		)
		self.doctor_other = User.objects.db_manager("default").create_user(
			username="doctor_op_timeline_other",
			email="doctor_op_timeline_other@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="Other",
		)
		self.billing = User.objects.db_manager("default").create_user(
			username="billing_op_timeline",
			email="billing_op_timeline@example.com",
			password="DummyPass123!",
			role=role_billing,
		)

		self.op_room_1 = Resource.objects.using("default").create(
			name="OP 1",
			type="room",
			active=True,
		)
		self.op_room_2 = Resource.objects.using("default").create(
			name="OP 2",
			type="room",
			active=True,
		)
		self.op_type = OperationType.objects.using("default").create(
			name="Timeline-OP",
			prep_duration=0,
			op_duration=60,
			post_duration=0,
			active=True,
		)

		# Fixed date for deterministic grouping.
		self.day = datetime(2030, 1, 7).date()  # Monday
		self.tz = timezone.get_current_timezone()

		# A: doctor user, running
		self.op_a = Operation.objects.using("default").create(
			patient_id=1,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room_1,
			op_type=self.op_type,
			start_time=timezone.make_aware(datetime.combine(self.day, time(10, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(11, 0)), self.tz),
			status="running",
			notes="A",
		)
		# B: other doctor, planned
		self.op_b = Operation.objects.using("default").create(
			patient_id=2,
			primary_surgeon=self.doctor_other,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room_1,
			op_type=self.op_type,
			start_time=timezone.make_aware(datetime.combine(self.day, time(12, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(13, 0)), self.tz),
			status="planned",
			notes="B",
		)
		# C: other doctor, confirmed
		self.op_c = Operation.objects.using("default").create(
			patient_id=3,
			primary_surgeon=self.doctor_other,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room_2,
			op_type=self.op_type,
			start_time=timezone.make_aware(datetime.combine(self.day, time(9, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(10, 0)), self.tz),
			status="confirmed",
			notes="C",
		)

	def test_grouping_live_and_rbac(self):
		admin_client = self._client_for(self.admin)
		doctor_client = self._client_for(self.doctor)

		frozen_now = timezone.make_aware(datetime.combine(self.day, time(10, 30)), self.tz)
		with patch("appointments.serializers.timezone.now", return_value=frozen_now), patch(
			"appointments.views.timezone.now", return_value=frozen_now
		):
			# 1) Grouping admin
			before = AuditLog.objects.using("default").count()
			r = admin_client.get("/api/op-timeline/", {"date": self.day.isoformat()})
			self.assertEqual(r.status_code, 200)
			self.assertEqual(AuditLog.objects.using("default").count(), before + 1)
			last = AuditLog.objects.using("default").order_by("-id").first()
			self.assertIsNotNone(last)
			self.assertEqual(last.action, "op_timeline_view")

			groups = r.data
			# OP 1 and OP 2 (sorted by room name)
			self.assertEqual(len(groups), 2)
			self.assertEqual(groups[0]["room"]["name"], "OP 1")
			self.assertEqual([o["id"] for o in groups[0]["operations"]], [self.op_a.id, self.op_b.id])
			self.assertEqual(groups[1]["room"]["name"], "OP 2")
			self.assertEqual([o["id"] for o in groups[1]["operations"]], [self.op_c.id])

			# progress only for running
			op_a_payload = groups[0]["operations"][0]
			self.assertGreater(float(op_a_payload["progress"]), 0.0)
			op_b_payload = groups[0]["operations"][1]
			self.assertEqual(float(op_b_payload["progress"]), 0.0)

			# 2) Live endpoint: only running/confirmed with start_time >= now-30min
			# now=10:30 => threshold 10:00
			r_live = admin_client.get("/api/op-timeline/live/")
			self.assertEqual(r_live.status_code, 200)
			live_groups = r_live.data
			# Only OP A (running at 10:00) qualifies; OP C starts at 09:00 -> excluded
			self.assertEqual(len(live_groups), 1)
			self.assertEqual(live_groups[0]["room"]["name"], "OP 1")
			self.assertEqual([o["id"] for o in live_groups[0]["operations"]], [self.op_a.id])

			# 3) RBAC: doctor sees only own OPs
			r_doc = doctor_client.get("/api/op-timeline/", {"date": self.day.isoformat()})
			self.assertEqual(r_doc.status_code, 200)
			doc_groups = r_doc.data
			self.assertEqual(len(doc_groups), 1)
			self.assertEqual(doc_groups[0]["room"]["name"], "OP 1")
			self.assertEqual([o["id"] for o in doc_groups[0]["operations"]], [self.op_a.id])
