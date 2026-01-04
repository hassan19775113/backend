from __future__ import annotations

from datetime import datetime, time
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import Appointment, AppointmentType, Operation, OperationType, PatientFlow, Resource
from praxi_backend.core.models import AuditLog, Role, User


class PatientFlowMiniTest(TestCase):
	"""Mini-Test: PatientFlow / Wartezimmer-Management.

	Szenario:
	- Flow A: registered → waiting → preparing → in_treatment → post_treatment → done
	- Wartezeit (arrival -> in_treatment) korrekt
	- Behandlungszeit (in_treatment -> done) korrekt
	- doctor sieht nur eigene Flows
	- Audit-Einträge korrekt

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
			username="admin_patient_flow",
			email="admin_patient_flow@example.com",
			password="DummyPass123!",
			role=role_admin,
		)
		self.assistant = User.objects.db_manager("default").create_user(
			username="assistant_patient_flow",
			email="assistant_patient_flow@example.com",
			password="DummyPass123!",
			role=role_assistant,
		)
		self.billing = User.objects.db_manager("default").create_user(
			username="billing_patient_flow",
			email="billing_patient_flow@example.com",
			password="DummyPass123!",
			role=role_billing,
		)
		self.doctor = User.objects.db_manager("default").create_user(
			username="doctor_patient_flow",
			email="doctor_patient_flow@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="Flow",
		)
		self.doctor_other = User.objects.db_manager("default").create_user(
			username="doctor_patient_flow_other",
			email="doctor_patient_flow_other@example.com",
			password="DummyPass123!",
			role=role_doctor,
			first_name="Dr",
			last_name="Other",
		)

		self.day = datetime(2030, 1, 7).date()  # Monday
		self.tz = timezone.get_current_timezone()

		self.appt_type = AppointmentType.objects.using("default").create(
			name="Sprechstunde",
			color="#ABCDEF",
			active=True,
		)
		self.op_type = OperationType.objects.using("default").create(
			name="Flow-OP",
			prep_duration=0,
			op_duration=60,
			post_duration=0,
			active=True,
		)
		self.op_room = Resource.objects.using("default").create(name="OP 1", type="room", active=True)

		self.appt = Appointment.objects.using("default").create(
			patient_id=1,
			type=self.appt_type,
			doctor=self.doctor,
			start_time=timezone.make_aware(datetime.combine(self.day, time(10, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(10, 30)), self.tz),
			status="scheduled",
			notes="A",
		)
		self.op_other = Operation.objects.using("default").create(
			patient_id=2,
			primary_surgeon=self.doctor_other,
			assistant=None,
			anesthesist=None,
			op_room=self.op_room,
			op_type=self.op_type,
			start_time=timezone.make_aware(datetime.combine(self.day, time(11, 0)), self.tz),
			end_time=timezone.make_aware(datetime.combine(self.day, time(12, 0)), self.tz),
			status="planned",
			notes="OP",
		)

	def test_flow_workflow_times_rbac_and_audit(self):
		admin_client = self._client_for(self.admin)
		doctor_client = self._client_for(self.doctor)
		billing_client = self._client_for(self.billing)

		arrival = timezone.make_aware(datetime.combine(self.day, time(8, 0)), self.tz)

		# Create flow for doctor's appointment
		r_create = admin_client.post(
			"/api/patient-flow/",
			{
				"appointment_id": self.appt.id,
				"status": PatientFlow.STATUS_REGISTERED,
				"arrival_time": arrival.isoformat(),
				"notes": "start",
			},
			format="json",
		)
		self.assertEqual(r_create.status_code, 201)
		flow_id = r_create.data["id"]

		# Another flow (not visible for doctor)
		r_create_other = admin_client.post(
			"/api/patient-flow/",
			{
				"operation_id": self.op_other.id,
				"status": PatientFlow.STATUS_REGISTERED,
				"arrival_time": arrival.isoformat(),
			},
			format="json",
		)
		self.assertEqual(r_create_other.status_code, 201)
		other_flow_id = r_create_other.data["id"]

		# GET list -> audit patient_flow_view
		before = AuditLog.objects.using("default").count()
		r_list = admin_client.get("/api/patient-flow/")
		self.assertEqual(r_list.status_code, 200)
		self.assertEqual(AuditLog.objects.using("default").count(), before + 1)
		self.assertEqual(AuditLog.objects.using("default").order_by("-id").first().action, "patient_flow_view")

		# Status transitions with deterministic audit timestamps.
		transitions = [
			(PatientFlow.STATUS_WAITING, time(8, 5)),
			(PatientFlow.STATUS_PREPARING, time(8, 10)),
			(PatientFlow.STATUS_IN_TREATMENT, time(8, 20)),
			(PatientFlow.STATUS_POST_TREATMENT, time(8, 50)),
			(PatientFlow.STATUS_DONE, time(9, 0)),
		]
		for new_status, t in transitions:
			frozen = timezone.make_aware(datetime.combine(self.day, t), self.tz)
			with patch("django.utils.timezone.now", return_value=frozen):
				before = AuditLog.objects.using("default").count()
				r = admin_client.patch(
					f"/api/patient-flow/{flow_id}/status/",
					{"status": new_status},
					format="json",
				)
				self.assertEqual(r.status_code, 200)
				self.assertEqual(AuditLog.objects.using("default").count(), before + 1)
				self.assertEqual(AuditLog.objects.using("default").order_by("-id").first().action, "patient_flow_status_update")

		# GET detail -> computed times
		frozen_now = timezone.make_aware(datetime.combine(self.day, time(9, 0)), self.tz)
		with patch("appointments.serializers.timezone.now", return_value=frozen_now):
			r_detail = admin_client.get(f"/api/patient-flow/{flow_id}/")
			self.assertEqual(r_detail.status_code, 200)
			self.assertEqual(int(r_detail.data["wait_time_minutes"]), 20)
			self.assertEqual(int(r_detail.data["treatment_time_minutes"]), 40)

		# done is read-only -> PATCH notes blocked
		r_done_patch = admin_client.patch(
			f"/api/patient-flow/{flow_id}/",
			{"notes": "x"},
			format="json",
		)
		self.assertIn(r_done_patch.status_code, (400, 403))

		# doctor sees only their flow
		r_doc_list = doctor_client.get("/api/patient-flow/")
		self.assertEqual(r_doc_list.status_code, 200)
		ids = [x["id"] for x in (r_doc_list.data or [])]
		self.assertEqual(ids, [flow_id])

		# live endpoint excludes done (but includes other non-done flows)
		r_live = admin_client.get("/api/patient-flow/live/")
		self.assertEqual(r_live.status_code, 200)
		live_ids = [x["id"] for x in (r_live.data or [])]
		self.assertNotIn(flow_id, live_ids)
		self.assertIn(other_flow_id, live_ids)

		# billing is read-only
		self.assertEqual(billing_client.get("/api/patient-flow/").status_code, 200)
		self.assertEqual(
			billing_client.post(
				"/api/patient-flow/",
				{"appointment_id": self.appt.id, "status": PatientFlow.STATUS_REGISTERED},
				format="json",
			).status_code,
			403,
		)
