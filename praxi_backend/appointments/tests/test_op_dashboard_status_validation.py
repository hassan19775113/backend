from __future__ import annotations

from datetime import datetime, time
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Operation, OperationType, Resource
from praxi_backend.core.models import AuditLog, Role, User


class OpDashboardStatusValidationMiniTest(TestCase):
	"""Mini-Test: Statusvalidierung OP-Dashboard.

	Szenarien:
	1) running nur wenn now >= start_time (400) + Audit: op_status_update
	2) running erlaubt wenn now >= start_time (200)
	3) done nur wenn vorher running (400)
	4) cancelled von überall (200)

	Nur default/system-DB; medical-DB nicht berühren.
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
			username="admin_op_dash_status",
			email="admin_op_dash_status@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor_op_dash_status",
			email="doctor_op_dash_status@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="Status",
		)

		self.client = self._client_for(self.admin)

		self.op_room = Resource.objects.using("default").create(
			name="OP 1",
			type="room",
			active=True,
		)
		self.op_type = OperationType.objects.using("default").create(
			name="Status-OP",
			prep_duration=0,
			op_duration=60,
			post_duration=0,
			active=True,
		)

		self.day = datetime(2030, 1, 7).date()  # Monday
		self.tz = timezone.get_current_timezone()

		self.start_10 = timezone.make_aware(datetime.combine(self.day, time(10, 0)), self.tz)
		self.end_11 = timezone.make_aware(datetime.combine(self.day, time(11, 0)), self.tz)

	def test_running_only_when_now_ge_start_time(self):
		op = Operation.objects.using("default").create(
			patient_id=1,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=self.start_10,
			end_time=self.end_11,
			status="confirmed",
			notes="CONF",
		)

		now_0950 = timezone.make_aware(datetime.combine(self.day, time(9, 50)), self.tz)
		with patch("appointments.views.timezone.now", return_value=now_0950):
			before = AuditLog.objects.using("default").count()
			r = self.client.patch(
				f"/api/op-dashboard/{op.id}/status/",
				{"status": "running"},
				format="json",
			)
			self.assertEqual(r.status_code, 400)
			self.assertEqual(AuditLog.objects.using("default").count(), before + 1)
			last = AuditLog.objects.using("default").order_by("-id").first()
			self.assertIsNotNone(last)
			self.assertEqual(last.action, "op_status_update")

	def test_running_allowed_when_now_ge_start_time(self):
		op = Operation.objects.using("default").create(
			patient_id=1,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=self.start_10,
			end_time=self.end_11,
			status="confirmed",
			notes="CONF",
		)

		now_1005 = timezone.make_aware(datetime.combine(self.day, time(10, 5)), self.tz)
		with patch("appointments.views.timezone.now", return_value=now_1005):
			r = self.client.patch(
				f"/api/op-dashboard/{op.id}/status/",
				{"status": "running"},
				format="json",
			)
			self.assertEqual(r.status_code, 200)
			self.assertEqual(r.data.get("status"), "running")

	def test_done_only_when_previous_running(self):
		op = Operation.objects.using("default").create(
			patient_id=1,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=self.start_10,
			end_time=self.end_11,
			status="confirmed",
			notes="CONF",
		)

		now_1010 = timezone.make_aware(datetime.combine(self.day, time(10, 10)), self.tz)
		with patch("appointments.views.timezone.now", return_value=now_1010):
			r = self.client.patch(
				f"/api/op-dashboard/{op.id}/status/",
				{"status": "done"},
				format="json",
			)
			self.assertEqual(r.status_code, 400)

	def test_cancelled_from_anywhere(self):
		op_planned = Operation.objects.using("default").create(
			patient_id=1,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=self.start_10,
			end_time=self.end_11,
			status="planned",
			notes="PLANNED",
		)
		op_running = Operation.objects.using("default").create(
			patient_id=2,
			primary_surgeon=self.doctor,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=self.start_10,
			end_time=self.end_11,
			status="running",
			notes="RUN",
		)

		now_1015 = timezone.make_aware(datetime.combine(self.day, time(10, 15)), self.tz)
		with patch("appointments.views.timezone.now", return_value=now_1015):
			r1 = self.client.patch(
				f"/api/op-dashboard/{op_planned.id}/status/",
				{"status": "cancelled"},
				format="json",
			)
			self.assertEqual(r1.status_code, 200)
			self.assertEqual(r1.data.get("status"), "cancelled")

			r2 = self.client.patch(
				f"/api/op-dashboard/{op_running.id}/status/",
				{"status": "cancelled"},
				format="json",
			)
			self.assertEqual(r2.status_code, 200)
			self.assertEqual(r2.data.get("status"), "cancelled")
