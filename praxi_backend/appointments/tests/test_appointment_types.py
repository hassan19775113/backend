from __future__ import annotations

from django.test import TestCase

from rest_framework.test import APIClient

from praxi_backend.appointments.models import AppointmentType
from praxi_backend.core.models import AuditLog, Role, User


class AppointmentTypeRBACAuditTests(TestCase):
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
		self.assertIsNone(last.patient_id)
		self.assertIsNotNone(last.timestamp)

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
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor_test",
			email="doctor_test@example.com",
			password="DummyPass123!",
			role=role_doctor,
		)
		self.billing = User.objects.db_manager("default").create_user(
			username="billing_test",
			email="billing_test@example.com",
			password="DummyPass123!",
			role=role_billing,
		)

		self.type_obj = AppointmentType.objects.using("default").create(
			name="Test Type",
			color="blue",
			duration_minutes=15,
			active=True,
		)

	def test_admin_crud_and_audit(self):
		client = self._client_for(self.admin)

		# GET list (200) + audit
		before = AuditLog.objects.using("default").count()
		r_list = client.get("/api/appointment-types/")
		self.assertEqual(r_list.status_code, 200)
		self._assert_last_audit(before_count=before, action="appointment_type_list", user=self.admin)

		# POST (201) + audit
		payload = {
			"name": "Sprechstunde",
			"color": "green",
			"duration_minutes": 20,
			"active": True,
		}
		before = AuditLog.objects.using("default").count()
		r_create = client.post("/api/appointment-types/", payload, format="json")
		self.assertEqual(r_create.status_code, 201)
		created_id = r_create.data.get("id")
		self.assertIsNotNone(created_id)
		self._assert_last_audit(before_count=before, action="appointment_type_create", user=self.admin)

		# GET detail (200) + audit
		before = AuditLog.objects.using("default").count()
		r_detail = client.get(f"/api/appointment-types/{created_id}/")
		self.assertEqual(r_detail.status_code, 200)
		self._assert_last_audit(before_count=before, action="appointment_type_view", user=self.admin)

		# PUT (200) + audit
		put_payload = {
			"name": "Sprechstunde (neu)",
			"color": "green",
			"duration_minutes": 25,
			"active": True,
		}
		before = AuditLog.objects.using("default").count()
		r_put = client.put(f"/api/appointment-types/{created_id}/", put_payload, format="json")
		self.assertEqual(r_put.status_code, 200)
		self._assert_last_audit(before_count=before, action="appointment_type_update", user=self.admin)

		# PATCH (200) + audit
		before = AuditLog.objects.using("default").count()
		r_patch = client.patch(
			f"/api/appointment-types/{created_id}/",
			{"active": False},
			format="json",
		)
		self.assertEqual(r_patch.status_code, 200)
		self._assert_last_audit(before_count=before, action="appointment_type_update", user=self.admin)

		# DELETE (204) + audit
		before = AuditLog.objects.using("default").count()
		r_delete = client.delete(f"/api/appointment-types/{created_id}/")
		self.assertEqual(r_delete.status_code, 204)
		self._assert_last_audit(before_count=before, action="appointment_type_delete", user=self.admin)

	def test_non_admin_write_forbidden_get_allowed_and_audit(self):
		for user in (self.assistant, self.doctor, self.billing):
			client = self._client_for(user)

			# GET list/detail allowed (200) + audit
			before = AuditLog.objects.using("default").count()
			r_list = client.get("/api/appointment-types/")
			self.assertEqual(r_list.status_code, 200)
			self._assert_last_audit(before_count=before, action="appointment_type_list", user=user)

			before = AuditLog.objects.using("default").count()
			r_detail = client.get(f"/api/appointment-types/{self.type_obj.id}/")
			self.assertEqual(r_detail.status_code, 200)
			self._assert_last_audit(before_count=before, action="appointment_type_view", user=user)

			# POST/PUT/PATCH/DELETE forbidden (403)
			r_post = client.post(
				"/api/appointment-types/",
				{"name": "X"},
				format="json",
			)
			self.assertEqual(r_post.status_code, 403)

			r_put = client.put(
				f"/api/appointment-types/{self.type_obj.id}/",
				{
					"name": "X",
					"color": None,
					"duration_minutes": None,
					"active": True,
				},
				format="json",
			)
			self.assertEqual(r_put.status_code, 403)

			r_patch = client.patch(
				f"/api/appointment-types/{self.type_obj.id}/",
				{"name": "X"},
				format="json",
			)
			self.assertEqual(r_patch.status_code, 403)

			r_delete = client.delete(f"/api/appointment-types/{self.type_obj.id}/")
			self.assertEqual(r_delete.status_code, 403)
