from __future__ import annotations

from django.test import TestCase

from rest_framework.test import APIClient

from praxi_backend.core.models import AuditLog, Role, User


class ResourceRBACMiniTest(TestCase):
	"""Mini-Test: RBAC für /api/resources/.

	- admin/assistant: CRUD
	- doctor/billing: read-only

	Nur default/system-DB.
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
			username="admin_res_rbac",
			email="admin_res_rbac@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.assistant = User.objects.db_manager("default").create_user(
			username="assistant_res_rbac",
			email="assistant_res_rbac@example.com",
			password="DummyPass123!",
			role=role_assistant,
		)
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor_res_rbac",
			email="doctor_res_rbac@example.com",
			password="DummyPass123!",
			role=role_doctor,
		)
		self.billing = User.objects.db_manager("default").create_user(
			username="billing_res_rbac",
			email="billing_res_rbac@example.com",
			password="DummyPass123!",
			role=role_billing,
		)

	def test_admin_and_assistant_crud_with_audit(self):
		for user in (self.admin, self.assistant):
			client = self._client_for(user)

			before = AuditLog.objects.using("default").count()
			r_list = client.get("/api/resources/")
			self.assertEqual(r_list.status_code, 200)
			self._assert_last_audit(before_count=before, action="resource_list", user=user)

			payload = {
				"name": "Ultraschallraum",
				"type": "room",
				"color": "#6A5ACD",
				"active": True,
			}
			before = AuditLog.objects.using("default").count()
			r_create = client.post("/api/resources/", payload, format="json")
			self.assertEqual(r_create.status_code, 201)
			resource_id = r_create.data.get("id")
			self.assertIsNotNone(resource_id)
			self._assert_last_audit(before_count=before, action="resource_create", user=user)

			r_detail = client.get(f"/api/resources/{resource_id}/")
			self.assertEqual(r_detail.status_code, 200)
			self.assertEqual(r_detail.data.get("name"), "Ultraschallraum")

			before = AuditLog.objects.using("default").count()
			r_patch = client.patch(
				f"/api/resources/{resource_id}/",
				{"color": "#123456"},
				format="json",
			)
			self.assertEqual(r_patch.status_code, 200)
			self._assert_last_audit(before_count=before, action="resource_update", user=user)

			before = AuditLog.objects.using("default").count()
			r_delete = client.delete(f"/api/resources/{resource_id}/")
			self.assertEqual(r_delete.status_code, 204)
			self._assert_last_audit(before_count=before, action="resource_delete", user=user)

	def test_doctor_and_billing_read_only(self):
		# Create one resource as admin for read checks.
		admin_client = self._client_for(self.admin)
		r_create = admin_client.post(
			"/api/resources/",
			{"name": "Ultraschallraum", "type": "room", "active": True},
			format="json",
		)
		self.assertEqual(r_create.status_code, 201)
		resource_id = r_create.data.get("id")
		self.assertIsNotNone(resource_id)

		for user in (self.doctor, self.billing):
			client = self._client_for(user)

			before = AuditLog.objects.using("default").count()
			r_list = client.get("/api/resources/")
			self.assertEqual(r_list.status_code, 200)
			self._assert_last_audit(before_count=before, action="resource_list", user=user)

			r_detail = client.get(f"/api/resources/{resource_id}/")
			self.assertEqual(r_detail.status_code, 200)

			r_post = client.post(
				"/api/resources/",
				{"name": "X", "type": "room", "active": True},
				format="json",
			)
			self.assertEqual(r_post.status_code, 403)

			r_patch = client.patch(
				f"/api/resources/{resource_id}/",
				{"name": "Y"},
				format="json",
			)
			self.assertEqual(r_patch.status_code, 403)

			r_delete = client.delete(f"/api/resources/{resource_id}/")
			self.assertEqual(r_delete.status_code, 403)
