from __future__ import annotations

from datetime import datetime, time

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Operation, OperationDevice, OperationType, Resource
from praxi_backend.core.models import AuditLog, Role, User


class OpStatsMiniTest(TestCase):
	"""Mini-Test: OP-Statistik Endpoints.

	Szenario:
	- Default-Öffnungszeit: 08:00–16:00 (8h) => 480 Minuten
	- OP-Raum OP 1
	- Gerät C-Bogen
	- OP-Typ 60 Minuten
	- 2 OPs à 60 Minuten im selben Raum + Gerät
	=> Raumauslastung: 120 / 480 = 0.25

	RBAC:
	- admin: alle Endpoints 200
	- doctor: nur overview + surgeons 200, rooms/devices/types 403
	- billing: read-only, alle Endpoints 200

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
			username="admin_op_stats",
			email="admin_op_stats@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor_op_stats",
			email="doctor_op_stats@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="Stats",
		)
		self.billing = User.objects.db_manager("default").create_user(
			username="billing_op_stats",
			email="billing_op_stats@example.com",
			password="DummyPass123!",
			role=role_billing,
		)

		self.op_room = Resource.objects.using("default").create(
			name="OP 1",
			type="room",
			active=True,
		)
		self.device = Resource.objects.using("default").create(
			name="C-Bogen",
			type="device",
			active=True,
		)
		self.op_type = OperationType.objects.using("default").create(
			name="Stats-OP",
			prep_duration=0,
			op_duration=60,
			post_duration=0,
			active=True,
		)

		self.day = datetime(2030, 1, 7).date()  # Monday
		self.tz = timezone.get_current_timezone()

		start_1 = timezone.make_aware(datetime.combine(self.day, time(8, 0)), self.tz)
		end_1 = timezone.make_aware(datetime.combine(self.day, time(9, 0)), self.tz)
		start_2 = timezone.make_aware(datetime.combine(self.day, time(9, 0)), self.tz)
		end_2 = timezone.make_aware(datetime.combine(self.day, time(10, 0)), self.tz)

		self.op1 = Operation.objects.using("default").create(
			patient_id=1,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=start_1,
			end_time=end_1,
			status="planned",
			notes="OP1",
		)
		self.op2 = Operation.objects.using("default").create(
			patient_id=2,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=start_2,
			end_time=end_2,
			status="planned",
			notes="OP2",
		)

		OperationDevice.objects.using("default").create(operation=self.op1, resource=self.device)
		OperationDevice.objects.using("default").create(operation=self.op2, resource=self.device)

	def test_stats_and_rbac(self):
		admin_client = self._client_for(self.admin)
		doctor_client = self._client_for(self.doctor)
		billing_client = self._client_for(self.billing)

		# admin: rooms -> utilization 0.25 + audit
		before = AuditLog.objects.using("default").count()
		r_rooms = admin_client.get("/api/op-stats/rooms/", {"date": self.day.isoformat()})
		self.assertEqual(r_rooms.status_code, 200)
		self.assertEqual(AuditLog.objects.using("default").count(), before + 1)
		last = AuditLog.objects.using("default").order_by("-id").first()
		self.assertIsNotNone(last)
		self.assertEqual(last.action, "op_stats_view")

		rooms = r_rooms.data.get("rooms") or []
		self.assertEqual(len(rooms), 1)
		room = rooms[0]
		self.assertEqual(int(room["total_minutes"]), 480)
		self.assertEqual(int(room["used_minutes"]), 120)
		self.assertAlmostEqual(float(room["utilization"]), 0.25, places=6)

		# admin: devices -> usage 120
		r_devices = admin_client.get("/api/op-stats/devices/", {"date": self.day.isoformat()})
		self.assertEqual(r_devices.status_code, 200)
		devices = r_devices.data.get("devices") or []
		self.assertEqual(len(devices), 1)
		self.assertEqual(int(devices[0]["usage_minutes"]), 120)

		# admin: types -> count 2, avg/min/max 60
		r_types = admin_client.get("/api/op-stats/types/", {"date": self.day.isoformat()})
		self.assertEqual(r_types.status_code, 200)
		types = r_types.data.get("types") or []
		self.assertEqual(len(types), 1)
		t = types[0]
		self.assertEqual(int(t["count"]), 2)
		self.assertAlmostEqual(float(t["avg_duration"]), 60.0, places=6)
		self.assertEqual(int(t["min_duration"]), 60)
		self.assertEqual(int(t["max_duration"]), 60)

		# admin: surgeons -> doctor has 2 ops
		r_surgeons = admin_client.get("/api/op-stats/surgeons/", {"date": self.day.isoformat()})
		self.assertEqual(r_surgeons.status_code, 200)
		surgeons = r_surgeons.data.get("surgeons") or []
		self.assertEqual(len(surgeons), 1)
		s = surgeons[0]
		self.assertEqual(int(s["op_count"]), 2)
		self.assertEqual(int(s["total_op_minutes"]), 120)
		self.assertAlmostEqual(float(s["average_op_duration"]), 60.0, places=6)

		# doctor: allowed overview + surgeons
		r_overview_doc = doctor_client.get("/api/op-stats/overview/", {"date": self.day.isoformat()})
		self.assertEqual(r_overview_doc.status_code, 200)
		self.assertEqual(int(r_overview_doc.data["op_count"]), 2)
		self.assertEqual(int(r_overview_doc.data["total_op_minutes"]), 120)
		self.assertAlmostEqual(float(r_overview_doc.data["average_op_duration"]), 60.0, places=6)

		r_surgeons_doc = doctor_client.get("/api/op-stats/surgeons/", {"date": self.day.isoformat()})
		self.assertEqual(r_surgeons_doc.status_code, 200)

		# doctor: forbidden endpoints
		self.assertEqual(
			doctor_client.get("/api/op-stats/rooms/", {"date": self.day.isoformat()}).status_code,
			403,
		)
		self.assertEqual(
			doctor_client.get("/api/op-stats/devices/", {"date": self.day.isoformat()}).status_code,
			403,
		)
		self.assertEqual(
			doctor_client.get("/api/op-stats/types/", {"date": self.day.isoformat()}).status_code,
			403,
		)

		# billing: allowed read-only stats
		self.assertEqual(
			billing_client.get("/api/op-stats/overview/", {"date": self.day.isoformat()}).status_code,
			200,
		)
		self.assertEqual(
			billing_client.get("/api/op-stats/types/", {"date": self.day.isoformat()}).status_code,
			200,
		)
