from __future__ import annotations

from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import DoctorHours, Operation, OperationType, PracticeHours, Resource
from praxi_backend.core.models import AuditLog, Role, User


class OperationRBACMiniTest(TestCase):
	"""Mini-Test: RBAC für /api/operations/.

	Szenarien:
	- admin/assistant: CRUD
	- doctor: read-only nur eigene OPs (Teammitglied)
	- billing: read-only

	Anforderung: Nur default/system-DB; medical DB bleibt unberührt.
	"""

	databases = {"default"}

	def _client_for(self, user: User) -> APIClient:
		client = APIClient()
		client.defaults["HTTP_HOST"] = "localhost"
		client.force_authenticate(user=user)
		return client

	def _assert_last_audit(self, *, before_count: int, action: str, user: User):
		after_count = AuditLog.objects.using("default").count()
		self.assertEqual(after_count, before_count + 1)

		last = AuditLog.objects.using("default").order_by("-id").first()
		self.assertIsNotNone(last)
		self.assertEqual(last.action, action)
		self.assertEqual(last.user_id, user.id)
		self.assertEqual(last.role_name, user.role.name)

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
			username="admin_ops_rbac",
			email="admin_ops_rbac@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.assistant = User.objects.db_manager("default").create_user(
			username="assistant_ops_rbac",
			email="assistant_ops_rbac@example.com",
			password="DummyPass123!",
			role=role_assistant,
		)
		self.doctor_a = User.objects.db_manager("default").create_user(
			username="doctor_ops_rbac_a",
			email="doctor_ops_rbac_a@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="A",
		)
		self.doctor_b = User.objects.db_manager("default").create_user(
			username="doctor_ops_rbac_b",
			email="doctor_ops_rbac_b@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="B",
		)
		self.billing = User.objects.db_manager("default").create_user(
			username="billing_ops_rbac",
			email="billing_ops_rbac@example.com",
			password="DummyPass123!",
			role=role_billing,
		)

		self.op_room = Resource.objects.using("default").create(
			name="OP-Raum 1",
			type="room",
			active=True,
		)
		self.device = Resource.objects.using("default").create(
			name="OP-Gerät 1",
			type="device",
			active=True,
		)
		self.op_type = OperationType.objects.using("default").create(
			name="Standard-OP",
			prep_duration=10,
			op_duration=30,
			post_duration=10,
			active=True,
		)

		# Deterministic weekday window for validations in OperationCreateUpdateSerializer.
		base = timezone.localdate() + timedelta(days=7)
		self.monday = base - timedelta(days=base.weekday())
		weekday = self.monday.weekday()
		self.assertEqual(weekday, 0)

		PracticeHours.objects.using("default").create(
			weekday=weekday,
			start_time=time(9, 0),
			end_time=time(13, 0),
			active=True,
		)
		DoctorHours.objects.using("default").create(
			doctor=self.doctor_a,
			weekday=weekday,
			start_time=time(9, 0),
			end_time=time(13, 0),
			active=True,
		)

	def test_admin_and_assistant_crud_with_audit(self):
		for user in (self.admin, self.assistant):
			client = self._client_for(user)

			before = AuditLog.objects.using("default").count()
			r_list = client.get("/api/operations/")
			self.assertEqual(r_list.status_code, 200)
			self._assert_last_audit(before_count=before, action="operation_list", user=user)

			tz = timezone.get_current_timezone()
			start = timezone.make_aware(datetime.combine(self.monday, time(10, 0)), tz)
			payload = {
				"patient_id": 123,
				"primary_surgeon": self.doctor_a.id,
				"assistant": None,
				"anesthesist": None,
				"op_room": self.op_room.id,
				"op_device_ids": [self.device.id],
				"op_type": self.op_type.id,
				"start_time": start.isoformat().replace("+00:00", "Z"),
				"status": "planned",
				"notes": f"RBAC_{user.role.name}",
			}

			before = AuditLog.objects.using("default").count()
			r_create = client.post("/api/operations/", payload, format="json")
			self.assertEqual(r_create.status_code, 201)
			operation_id = r_create.data.get("id")
			self.assertIsNotNone(operation_id)
			self._assert_last_audit(before_count=before, action="operation_create", user=user)

			r_detail = client.get(f"/api/operations/{operation_id}/")
			self.assertEqual(r_detail.status_code, 200)

			before = AuditLog.objects.using("default").count()
			r_patch = client.patch(
				f"/api/operations/{operation_id}/",
				{"notes": "UPDATED"},
				format="json",
			)
			self.assertEqual(r_patch.status_code, 200)
			self._assert_last_audit(before_count=before, action="operation_update", user=user)

			before = AuditLog.objects.using("default").count()
			r_delete = client.delete(f"/api/operations/{operation_id}/")
			self.assertEqual(r_delete.status_code, 204)
			self._assert_last_audit(before_count=before, action="operation_delete", user=user)

	def test_doctor_read_only_only_own_ops(self):
		tz = timezone.get_current_timezone()
		start = timezone.make_aware(datetime(2030, 1, 7, 10, 0, 0), tz)
		end = start + timedelta(minutes=50)

		op_a = Operation.objects.using("default").create(
			patient_id=1,
			primary_surgeon=self.doctor_a,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=start,
			end_time=end,
			status="planned",
			notes="OWN",
		)
		op_a.op_devices.add(self.device)

		op_b = Operation.objects.using("default").create(
			patient_id=2,
			primary_surgeon=self.doctor_b,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=start + timedelta(hours=2),
			end_time=end + timedelta(hours=2),
			status="planned",
			notes="OTHER",
		)

		client = self._client_for(self.doctor_a)

		before = AuditLog.objects.using("default").count()
		r_list = client.get("/api/operations/")
		self.assertEqual(r_list.status_code, 200)
		self._assert_last_audit(before_count=before, action="operation_list", user=self.doctor_a)

		# DRF uses pagination in settings_dev/settings_prod by default.
		payload = r_list.data or {}
		rows = payload.get("results", payload) if isinstance(payload, dict) else payload
		ids = [row.get("id") for row in (rows or [])]
		self.assertIn(op_a.id, ids)
		self.assertNotIn(op_b.id, ids)

		r_detail_own = client.get(f"/api/operations/{op_a.id}/")
		self.assertEqual(r_detail_own.status_code, 200)

		r_detail_other = client.get(f"/api/operations/{op_b.id}/")
		self.assertIn(r_detail_other.status_code, (403, 404))

		r_post = client.post(
			"/api/operations/",
			{"patient_id": 1},
			format="json",
		)
		self.assertEqual(r_post.status_code, 403)

		r_patch = client.patch(
			f"/api/operations/{op_a.id}/",
			{"notes": "X"},
			format="json",
		)
		self.assertEqual(r_patch.status_code, 403)

		r_delete = client.delete(f"/api/operations/{op_a.id}/")
		self.assertEqual(r_delete.status_code, 403)

	def test_billing_read_only(self):
		tz = timezone.get_current_timezone()
		start = timezone.make_aware(datetime(2030, 1, 7, 10, 0, 0), tz)
		end = start + timedelta(minutes=50)

		op = Operation.objects.using("default").create(
			patient_id=1,
			primary_surgeon=self.doctor_a,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=start,
			end_time=end,
			status="planned",
			notes="BILLING",
		)

		client = self._client_for(self.billing)

		before = AuditLog.objects.using("default").count()
		r_list = client.get("/api/operations/")
		self.assertEqual(r_list.status_code, 200)
		self._assert_last_audit(before_count=before, action="operation_list", user=self.billing)

		r_detail = client.get(f"/api/operations/{op.id}/")
		self.assertEqual(r_detail.status_code, 200)

		r_post = client.post(
			"/api/operations/",
			{"patient_id": 1},
			format="json",
		)
		self.assertEqual(r_post.status_code, 403)

		r_patch = client.patch(
			f"/api/operations/{op.id}/",
			{"notes": "X"},
			format="json",
		)
		self.assertEqual(r_patch.status_code, 403)

		r_delete = client.delete(f"/api/operations/{op.id}/")
		self.assertEqual(r_delete.status_code, 403)
