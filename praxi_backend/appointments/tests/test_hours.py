from __future__ import annotations

from django.test import TestCase

from rest_framework.test import APIClient

from praxi_backend.core.models import AuditLog, Role, User


class HoursMiniTests(TestCase):
	databases = {"default"}

	def _client_for(self, user: User) -> APIClient:
		client = APIClient()
		client.defaults["HTTP_HOST"] = "localhost"
		client.force_authenticate(user=user)
		return client

	def _rows(self, payload):
		if isinstance(payload, dict):
			return payload.get("results", payload)
		return payload

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
		self.doctor1 = User.objects.db_manager("default").create_user(
			username="doctor1_test",
			email="doctor1_test@example.com",
			password="DummyPass123!",
			role=role_doctor,
		)
		self.doctor2 = User.objects.db_manager("default").create_user(
			username="doctor2_test",
			email="doctor2_test@example.com",
			password="DummyPass123!",
			role=role_doctor,
		)
		self.billing = User.objects.db_manager("default").create_user(
			username="billing_test",
			email="billing_test@example.com",
			password="DummyPass123!",
			role=role_billing,
		)

	def test_hours_flow_rbac_and_audit(self):
		admin_client = self._client_for(self.admin)
		assistant_client = self._client_for(self.assistant)
		doctor_client = self._client_for(self.doctor1)
		billing_client = self._client_for(self.billing)

		# 1) admin creates practice hours -> 201 + audit
		before = AuditLog.objects.using("default").count()
		r_ph = admin_client.post(
			"/api/practice-hours/",
			{
				"weekday": 0,
				"start_time": "09:00:00",
				"end_time": "17:00:00",
				"active": True,
			},
			format="json",
		)
		self.assertEqual(r_ph.status_code, 201)
		practice_hours_id = r_ph.data.get("id")
		self.assertIsNotNone(practice_hours_id)
		self._assert_last_audit(before_count=before, action="practice_hours_create", user=self.admin)

		# 2) assistant creates doctor hours for doctor1 and doctor2 -> 201 + audit
		before = AuditLog.objects.using("default").count()
		r_dh_1 = assistant_client.post(
			"/api/doctor-hours/",
			{
				"doctor": self.doctor1.id,
				"weekday": 0,
				"start_time": "10:00:00",
				"end_time": "12:00:00",
				"active": True,
			},
			format="json",
		)
		self.assertEqual(r_dh_1.status_code, 201)
		doctor1_hours_id = r_dh_1.data.get("id")
		self.assertIsNotNone(doctor1_hours_id)
		self._assert_last_audit(before_count=before, action="doctor_hours_create", user=self.assistant)

		before = AuditLog.objects.using("default").count()
		r_dh_2 = assistant_client.post(
			"/api/doctor-hours/",
			{
				"doctor": self.doctor2.id,
				"weekday": 0,
				"start_time": "13:00:00",
				"end_time": "15:00:00",
				"active": True,
			},
			format="json",
		)
		self.assertEqual(r_dh_2.status_code, 201)
		doctor2_hours_id = r_dh_2.data.get("id")
		self.assertIsNotNone(doctor2_hours_id)
		self._assert_last_audit(before_count=before, action="doctor_hours_create", user=self.assistant)

		# 3) doctor1 sees only own doctor hours in list -> 200 + audit
		before = AuditLog.objects.using("default").count()
		r_list = doctor_client.get("/api/doctor-hours/")
		self.assertEqual(r_list.status_code, 200)
		self._assert_last_audit(before_count=before, action="doctor_hours_list", user=self.doctor1)

		rows = self._rows(r_list.data)
		self.assertIsInstance(rows, list)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["doctor"], self.doctor1.id)

		# 4) doctor1 cannot retrieve doctor2 hours (queryset filtered) -> 404
		r_forbidden_detail = doctor_client.get(f"/api/doctor-hours/{doctor2_hours_id}/")
		self.assertEqual(r_forbidden_detail.status_code, 404)

		# 5) billing cannot write practice/doctor hours -> 403
		r_billing_ph = billing_client.post(
			"/api/practice-hours/",
			{"weekday": 1, "start_time": "09:00:00", "end_time": "10:00:00", "active": True},
			format="json",
		)
		self.assertEqual(r_billing_ph.status_code, 403)

		r_billing_dh = billing_client.post(
			"/api/doctor-hours/",
			{
				"doctor": self.doctor1.id,
				"weekday": 1,
				"start_time": "09:00:00",
				"end_time": "10:00:00",
				"active": True,
			},
			format="json",
		)
		self.assertEqual(r_billing_dh.status_code, 403)

		# 6) billing can read practice hours list -> 200 + audit
		before = AuditLog.objects.using("default").count()
		r_ph_list = billing_client.get("/api/practice-hours/")
		self.assertEqual(r_ph_list.status_code, 200)
		self._assert_last_audit(before_count=before, action="practice_hours_list", user=self.billing)
