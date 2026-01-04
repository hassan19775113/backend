"""Tests for Appointment CRUD endpoints.

Tests cover:
- List appointments (GET /api/appointments/)
- Create appointments (POST /api/appointments/)
- Retrieve appointment (GET /api/appointments/<pk>/)
- Update appointment (PUT/PATCH /api/appointments/<pk>/)
- Delete appointment (DELETE /api/appointments/<pk>/)
- RBAC (read/write roles)
- Validations (end_time > start_time, date validations)
- Audit logging via log_patient_action

Uses only the default/system test DB.
Does NOT query medical.Patient - uses patient_id as integer.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient

from praxi_backend.core.models import Role, User
from praxi_backend.appointments.models import Appointment, AppointmentType


class AppointmentCRUDTest(TestCase):
    """Tests for /api/appointments/ CRUD endpoints."""

    databases = {"default"}

    def setUp(self):
        # Create roles
        self.role_admin, _ = Role.objects.using("default").get_or_create(
            name="admin",
            defaults={"label": "Administrator"},
        )
        self.role_assistant, _ = Role.objects.using("default").get_or_create(
            name="assistant",
            defaults={"label": "Assistent"},
        )
        self.role_doctor, _ = Role.objects.using("default").get_or_create(
            name="doctor",
            defaults={"label": "Arzt"},
        )
        self.role_billing, _ = Role.objects.using("default").get_or_create(
            name="billing",
            defaults={"label": "Abrechnung"},
        )

        # Create users
        self.admin = User.objects.db_manager("default").create_user(
            username="admin_appt_test",
            email="admin_appt@example.com",
            password="DummyPass123!",
            role=self.role_admin,
        )
        self.assistant = User.objects.db_manager("default").create_user(
            username="assistant_appt_test",
            email="assistant_appt@example.com",
            password="DummyPass123!",
            role=self.role_assistant,
        )
        self.doctor = User.objects.db_manager("default").create_user(
            username="doctor_appt_test",
            email="doctor_appt@example.com",
            password="DummyPass123!",
            role=self.role_doctor,
        )
        self.doctor2 = User.objects.db_manager("default").create_user(
            username="doctor2_appt_test",
            email="doctor2_appt@example.com",
            password="DummyPass123!",
            role=self.role_doctor,
        )
        self.billing = User.objects.db_manager("default").create_user(
            username="billing_appt_test",
            email="billing_appt@example.com",
            password="DummyPass123!",
            role=self.role_billing,
        )

        # Create an appointment type
        self.appt_type = AppointmentType.objects.using("default").create(
            name="Checkup",
            color="#2E8B57",
            duration_minutes=30,
            active=True,
        )

        # Future date for valid appointments
        self.tomorrow = timezone.now() + timedelta(days=1)
        self.start_time = self.tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        self.end_time = self.tomorrow.replace(hour=10, minute=30, second=0, microsecond=0)

        # Create test appointment
        self.appointment = Appointment.objects.using("default").create(
            patient_id=99999,  # Integer dummy, no medical DB query
            doctor=self.doctor,
            type=self.appt_type,
            start_time=self.start_time,
            end_time=self.end_time,
            status=Appointment.STATUS_SCHEDULED,
            notes="Test appointment",
        )

        self.client = APIClient()
        self.client.defaults["HTTP_HOST"] = "localhost"

    def _client_for(self, user: User) -> APIClient:
        client = APIClient()
        client.defaults["HTTP_HOST"] = "localhost"
        client.force_authenticate(user=user)
        return client

    # ========== LIST TESTS ==========

    def test_list_as_admin_returns_all_appointments(self):
        """Admin can list all appointments."""
        client = self._client_for(self.admin)
        response = client.get("/api/appointments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["patient_id"], 99999)

    def test_list_as_assistant_returns_all_appointments(self):
        """Assistant can list all appointments."""
        client = self._client_for(self.assistant)
        response = client.get("/api/appointments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_as_doctor_returns_only_own_appointments(self):
        """Doctor can only see their own appointments."""
        # Create appointment for doctor2
        Appointment.objects.using("default").create(
            patient_id=88888,
            doctor=self.doctor2,
            start_time=self.start_time + timedelta(hours=1),
            end_time=self.end_time + timedelta(hours=1),
            status=Appointment.STATUS_SCHEDULED,
        )

        # doctor should only see their own appointment
        client = self._client_for(self.doctor)
        response = client.get("/api/appointments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["patient_id"], 99999)

        # doctor2 should only see their own appointment
        client2 = self._client_for(self.doctor2)
        response2 = client2.get("/api/appointments/")

        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response2.data), 1)
        self.assertEqual(response2.data[0]["patient_id"], 88888)

    def test_list_as_billing_returns_all_appointments(self):
        """Billing can list all appointments (read-only)."""
        client = self._client_for(self.billing)
        response = client.get("/api/appointments/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_list_unauthenticated_forbidden(self):
        """Unauthenticated requests are forbidden."""
        response = self.client.get("/api/appointments/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== CREATE TESTS ==========

    @patch("praxi_backend.appointments.views.log_patient_action")
    def test_create_as_admin_success(self, mock_log):
        """Admin can create an appointment."""
        client = self._client_for(self.admin)
        data = {
            "patient_id": 77777,
            "doctor": self.doctor.id,
            "type": self.appt_type.id,
            "start_time": (self.start_time + timedelta(days=1)).isoformat(),
            "end_time": (self.end_time + timedelta(days=1)).isoformat(),
            "status": "scheduled",
            "notes": "New appointment",
        }

        response = client.post("/api/appointments/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Appointment.objects.using("default").count(), 2)

        created = Appointment.objects.using("default").get(patient_id=77777)
        self.assertEqual(created.doctor_id, self.doctor.id)
        self.assertEqual(created.notes, "New appointment")

        # Verify logging was called
        mock_log.assert_called()
        # Find the appointment_create call
        calls = [c for c in mock_log.call_args_list if c[0][1] == "appointment_create"]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0][2], 77777)  # patient_id

    @patch("praxi_backend.appointments.views.log_patient_action")
    def test_create_as_assistant_success(self, mock_log):
        """Assistant can create an appointment."""
        client = self._client_for(self.assistant)
        data = {
            "patient_id": 66666,
            "doctor": self.doctor.id,
            "start_time": (self.start_time + timedelta(days=2)).isoformat(),
            "end_time": (self.end_time + timedelta(days=2)).isoformat(),
            "status": "scheduled",
        }

        response = client.post("/api/appointments/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_log.assert_called()

    @patch("praxi_backend.appointments.views.log_patient_action")
    def test_create_as_doctor_own_appointment_success(self, mock_log):
        """Doctor can create an appointment for themselves."""
        client = self._client_for(self.doctor)
        data = {
            "patient_id": 55555,
            "doctor": self.doctor.id,  # Own ID
            "start_time": (self.start_time + timedelta(days=3)).isoformat(),
            "end_time": (self.end_time + timedelta(days=3)).isoformat(),
            "status": "scheduled",
        }

        response = client.post("/api/appointments/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_log.assert_called()

    def test_create_as_doctor_for_other_doctor_forbidden(self):
        """Doctor cannot create appointment for another doctor."""
        client = self._client_for(self.doctor)
        data = {
            "patient_id": 44444,
            "doctor": self.doctor2.id,  # Different doctor!
            "start_time": (self.start_time + timedelta(days=4)).isoformat(),
            "end_time": (self.end_time + timedelta(days=4)).isoformat(),
            "status": "scheduled",
        }

        response = client.post("/api/appointments/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("doctor", str(response.data))

    def test_create_as_billing_forbidden(self):
        """Billing cannot create appointments (read-only)."""
        client = self._client_for(self.billing)
        data = {
            "patient_id": 33333,
            "doctor": self.doctor.id,
            "start_time": (self.start_time + timedelta(days=5)).isoformat(),
            "end_time": (self.end_time + timedelta(days=5)).isoformat(),
            "status": "scheduled",
        }

        response = client.post("/api/appointments/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== VALIDATION TESTS ==========

    def test_create_end_time_before_start_time_fails(self):
        """end_time must be after start_time."""
        client = self._client_for(self.admin)
        data = {
            "patient_id": 22222,
            "doctor": self.doctor.id,
            "start_time": self.end_time.isoformat(),  # Swapped!
            "end_time": self.start_time.isoformat(),
            "status": "scheduled",
        }

        response = client.post("/api/appointments/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_time", str(response.data))

    def test_create_invalid_patient_id_fails(self):
        """patient_id must be a positive integer."""
        client = self._client_for(self.admin)
        data = {
            "patient_id": -1,
            "doctor": self.doctor.id,
            "start_time": (self.start_time + timedelta(days=6)).isoformat(),
            "end_time": (self.end_time + timedelta(days=6)).isoformat(),
            "status": "scheduled",
        }

        response = client.post("/api/appointments/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("patient_id", str(response.data))

    # ========== RETRIEVE TESTS ==========

    @patch("praxi_backend.appointments.views.log_patient_action")
    def test_retrieve_as_admin_success(self, mock_log):
        """Admin can retrieve any appointment."""
        client = self._client_for(self.admin)
        response = client.get(f"/api/appointments/{self.appointment.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["patient_id"], 99999)
        self.assertEqual(response.data["id"], self.appointment.pk)

        # Verify logging
        mock_log.assert_called()
        calls = [c for c in mock_log.call_args_list if c[0][1] == "appointment_view"]
        self.assertEqual(len(calls), 1)

    def test_retrieve_as_doctor_own_appointment_success(self):
        """Doctor can retrieve their own appointment."""
        client = self._client_for(self.doctor)
        response = client.get(f"/api/appointments/{self.appointment.pk}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["patient_id"], 99999)

    def test_retrieve_as_doctor_other_appointment_forbidden(self):
        """Doctor cannot retrieve another doctor's appointment."""
        # Create appointment for doctor2
        other_appt = Appointment.objects.using("default").create(
            patient_id=11111,
            doctor=self.doctor2,
            start_time=self.start_time + timedelta(hours=2),
            end_time=self.end_time + timedelta(hours=2),
            status=Appointment.STATUS_SCHEDULED,
        )

        client = self._client_for(self.doctor)
        response = client.get(f"/api/appointments/{other_appt.pk}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_not_found(self):
        """Non-existent appointment returns 404."""
        client = self._client_for(self.admin)
        response = client.get("/api/appointments/99999/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== UPDATE TESTS ==========

    @patch("praxi_backend.appointments.views.log_patient_action")
    def test_update_as_admin_success(self, mock_log):
        """Admin can update any appointment."""
        client = self._client_for(self.admin)
        data = {
            "patient_id": 99999,
            "doctor": self.doctor.id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "status": "confirmed",
            "notes": "Updated notes",
        }

        response = client.put(f"/api/appointments/{self.appointment.pk}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "confirmed")
        self.assertEqual(self.appointment.notes, "Updated notes")

        # Verify logging
        mock_log.assert_called()
        calls = [c for c in mock_log.call_args_list if c[0][1] == "appointment_update"]
        self.assertEqual(len(calls), 1)

    @patch("praxi_backend.appointments.views.log_patient_action")
    def test_partial_update_as_assistant_success(self, mock_log):
        """Assistant can partially update an appointment."""
        client = self._client_for(self.assistant)
        data = {"notes": "Partial update"}

        response = client.patch(f"/api/appointments/{self.appointment.pk}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.notes, "Partial update")

    def test_update_as_doctor_own_appointment_success(self):
        """Doctor can update their own appointment."""
        client = self._client_for(self.doctor)
        data = {"notes": "Doctor update"}

        response = client.patch(f"/api/appointments/{self.appointment.pk}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.notes, "Doctor update")

    def test_update_as_doctor_other_appointment_forbidden(self):
        """Doctor cannot update another doctor's appointment."""
        # Create appointment for doctor2
        other_appt = Appointment.objects.using("default").create(
            patient_id=10101,
            doctor=self.doctor2,
            start_time=self.start_time + timedelta(hours=3),
            end_time=self.end_time + timedelta(hours=3),
            status=Appointment.STATUS_SCHEDULED,
        )

        client = self._client_for(self.doctor)
        data = {"notes": "Should fail"}

        response = client.patch(f"/api/appointments/{other_appt.pk}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_as_billing_forbidden(self):
        """Billing cannot update appointments (read-only)."""
        client = self._client_for(self.billing)
        data = {"notes": "Should fail"}

        response = client.patch(f"/api/appointments/{self.appointment.pk}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== DELETE TESTS ==========

    @patch("praxi_backend.appointments.views.log_patient_action")
    def test_delete_as_admin_success(self, mock_log):
        """Admin can delete an appointment."""
        client = self._client_for(self.admin)
        pk = self.appointment.pk

        response = client.delete(f"/api/appointments/{pk}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Appointment.objects.using("default").filter(pk=pk).exists())

        # Verify logging
        mock_log.assert_called()
        calls = [c for c in mock_log.call_args_list if c[0][1] == "appointment_delete"]
        self.assertEqual(len(calls), 1)

    def test_delete_as_doctor_own_appointment_success(self):
        """Doctor can delete their own appointment."""
        client = self._client_for(self.doctor)
        pk = self.appointment.pk

        response = client.delete(f"/api/appointments/{pk}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_delete_as_doctor_other_appointment_forbidden(self):
        """Doctor cannot delete another doctor's appointment."""
        # Create appointment for doctor2
        other_appt = Appointment.objects.using("default").create(
            patient_id=20202,
            doctor=self.doctor2,
            start_time=self.start_time + timedelta(hours=4),
            end_time=self.end_time + timedelta(hours=4),
            status=Appointment.STATUS_SCHEDULED,
        )

        client = self._client_for(self.doctor)
        response = client.delete(f"/api/appointments/{other_appt.pk}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_as_billing_forbidden(self):
        """Billing cannot delete appointments (read-only)."""
        client = self._client_for(self.billing)
        response = client.delete(f"/api/appointments/{self.appointment.pk}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== RBAC SUMMARY TESTS ==========

    def test_rbac_read_roles(self):
        """Verify read access for all allowed roles."""
        for user in [self.admin, self.assistant, self.doctor, self.billing]:
            client = self._client_for(user)
            response = client.get("/api/appointments/")
            self.assertIn(
                response.status_code,
                [status.HTTP_200_OK],
                f"{user.role.name} should have read access",
            )

    def test_rbac_write_roles(self):
        """Verify write access for admin, assistant, doctor; denied for billing."""
        base_data = {
            "patient_id": 12121,
            "doctor": self.doctor.id,
            "status": "scheduled",
        }

        # Admin can write
        client = self._client_for(self.admin)
        data = {
            **base_data,
            "patient_id": 12121,
            "start_time": (self.start_time + timedelta(days=10)).isoformat(),
            "end_time": (self.end_time + timedelta(days=10)).isoformat(),
        }
        response = client.post("/api/appointments/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Assistant can write
        data = {
            **base_data,
            "patient_id": 12122,
            "start_time": (self.start_time + timedelta(days=11)).isoformat(),
            "end_time": (self.end_time + timedelta(days=11)).isoformat(),
        }
        client = self._client_for(self.assistant)
        response = client.post("/api/appointments/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Doctor can write (own appointments)
        data = {
            **base_data,
            "patient_id": 12123,
            "start_time": (self.start_time + timedelta(days=12)).isoformat(),
            "end_time": (self.end_time + timedelta(days=12)).isoformat(),
        }
        client = self._client_for(self.doctor)
        response = client.post("/api/appointments/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Billing cannot write
        data = {
            **base_data,
            "patient_id": 12124,
            "start_time": (self.start_time + timedelta(days=13)).isoformat(),
            "end_time": (self.end_time + timedelta(days=13)).isoformat(),
        }
        client = self._client_for(self.billing)
        response = client.post("/api/appointments/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
