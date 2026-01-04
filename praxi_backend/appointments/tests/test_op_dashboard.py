from __future__ import annotations

from datetime import datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Operation, OperationType, Resource
from praxi_backend.core.models import AuditLog, Role, User


class OpDashboardMiniTest(TestCase):
	"""Mini-Test: OP-Dashboard Endpoints.

	- Operation 10:00–11:00, status=running, now=10:30 -> progress=0.5
	- PATCH status=done -> 200 für admin, 403 für doctor
	- GET /api/op-dashboard/ -> OPs sortiert nach start_time
	- GET /api/op-dashboard/live/ -> nur laufende OPs

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
			username="admin_op_dash",
			email="admin_op_dash@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor_op_dash",
			email="doctor_op_dash@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="Dash",
		)

		self.op_room = Resource.objects.using("default").create(
			name="OP 1",
			type="room",
			active=True,
		)
		self.op_type = OperationType.objects.using("default").create(
			name="Dash-OP",
			prep_duration=0,
			op_duration=60,
			post_duration=0,
			active=True,
		)

		# Fixed date/time for deterministic progress math.
		self.day = datetime(2030, 1, 7).date()  # Monday
		self.tz = timezone.get_current_timezone()

		self.op_running = Operation.objects.using("default").create(
			patient_id=1,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=timezone.make_aware(datetime.combine(self.day, time(10, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(11, 0)), self.tz),
			status="running",
			notes="RUN",
		)
		self.op_planned = Operation.objects.using("default").create(
			patient_id=2,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=timezone.make_aware(datetime.combine(self.day, time(9, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(10, 0)), self.tz),
			status="planned",
			notes="PLANNED",
		)

	def test_progress_and_live_and_sort_and_patch_rbac(self):
		admin_client = self._client_for(self.admin)
		doctor_client = self._client_for(self.doctor)

		frozen_now = timezone.make_aware(datetime.combine(self.day, time(10, 30)), self.tz)
		with patch("appointments.serializers.timezone.now", return_value=frozen_now), patch(
			"appointments.views.timezone.now", return_value=frozen_now
		):
			before = AuditLog.objects.using("default").count()
			r = admin_client.get("/api/op-dashboard/", {"date": self.day.isoformat()})
			self.assertEqual(r.status_code, 200)
			# audit
			self.assertEqual(AuditLog.objects.using("default").count(), before + 1)
			last = AuditLog.objects.using("default").order_by("-id").first()
			self.assertEqual(last.action, "op_dashboard_view")

			ops = r.data.get("operations") or []
			# Sorted by start_time: 09:00 first, then 10:00
			self.assertEqual([o["id"] for o in ops], [self.op_planned.id, self.op_running.id])

			run = [o for o in ops if o["id"] == self.op_running.id][0]
			self.assertAlmostEqual(float(run["progress"]), 0.5, places=6)
			self.assertEqual(run["color"], self.op_type.color)

			r_live = admin_client.get("/api/op-dashboard/live/")
			self.assertEqual(r_live.status_code, 200)
			live_ops = r_live.data.get("operations") or []
			self.assertEqual([o["id"] for o in live_ops], [self.op_running.id])

			# PATCH status=done: admin allowed
			before = AuditLog.objects.using("default").count()
			r_patch = admin_client.patch(
				f"/api/op-dashboard/{self.op_running.id}/status/",
				{"status": "done"},
				format="json",
			)
			self.assertEqual(r_patch.status_code, 200)
			self.assertEqual(r_patch.data.get("status"), "done")
			self.assertEqual(AuditLog.objects.using("default").count(), before + 1)
			last = AuditLog.objects.using("default").order_by("-id").first()
			self.assertEqual(last.action, "op_status_update")

			# PATCH status=done: doctor forbidden
			r_patch_doc = doctor_client.patch(
				f"/api/op-dashboard/{self.op_running.id}/status/",
				{"status": "done"},
				format="json",
			)
			self.assertEqual(r_patch_doc.status_code, 403)
