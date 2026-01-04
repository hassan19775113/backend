from __future__ import annotations

from datetime import date
from unittest.mock import patch

from django.test import TestCase

from rest_framework.test import APIClient

from core.models import Role, User
from patients.models import Patient


class PatientAPITest(TestCase):
    """Tests for /api/patients/ endpoints.

    Uses only the default/system test DB.
    RBAC: admin, assistant, doctor = full access; billing = read-only
    """

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
            username="admin_patient_test",
            email="admin_patient@example.com",
            password="DummyPass123!",
            role=self.role_admin,
        )
        self.assistant = User.objects.db_manager("default").create_user(
            username="assistant_patient_test",
            email="assistant_patient@example.com",
            password="DummyPass123!",
            role=self.role_assistant,
        )
        self.doctor = User.objects.db_manager("default").create_user(
            username="doctor_patient_test",
            email="doctor_patient@example.com",
            password="DummyPass123!",
            role=self.role_doctor,
        )
        self.billing = User.objects.db_manager("default").create_user(
            username="billing_patient_test",
            email="billing_patient@example.com",
            password="DummyPass123!",
            role=self.role_billing,
        )

        # Create test patient
        self.patient = Patient.objects.using("default").create(
            patient_id=1001,
            first_name="Max",
            last_name="Mustermann",
            birth_date=date(1990, 5, 15),
        )

        self.client = APIClient()
        self.client.defaults["HTTP_HOST"] = "localhost"

    def _client_for(self, user: User) -> APIClient:
        client = APIClient()
        client.defaults["HTTP_HOST"] = "localhost"
        client.force_authenticate(user=user)
        return client

    # ========== LIST TESTS ==========

    def test_list_as_admin_returns_patients(self):
        """Admin can list all patients."""
        client = self._client_for(self.admin)
        response = client.get("/api/patients/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["patient_id"], 1001)

    def test_list_as_doctor_returns_patients(self):
        """Doctor can list all patients."""
        client = self._client_for(self.doctor)
        response = client.get("/api/patients/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_list_as_assistant_returns_patients(self):
        """Assistant can list all patients."""
        client = self._client_for(self.assistant)
        response = client.get("/api/patients/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_list_as_billing_returns_patients(self):
        """Billing can list all patients (read-only)."""
        client = self._client_for(self.billing)
        response = client.get("/api/patients/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_list_unauthenticated_forbidden(self):
        """Unauthenticated requests are forbidden."""
        response = self.client.get("/api/patients/")

        self.assertEqual(response.status_code, 401)

    # ========== CREATE TESTS ==========

    @patch("praxi_backend.patients.views.log_patient_action")
    def test_create_as_admin_success(self, mock_log):
        """Admin can create a patient."""
        client = self._client_for(self.admin)
        data = {
            "patient_id": 2001,
            "first_name": "Erika",
            "last_name": "Musterfrau",
            "birth_date": "1985-03-20",
        }

        response = client.post("/api/patients/", data, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Patient.objects.using("default").count(), 2)

        created = Patient.objects.using("default").get(patient_id=2001)
        self.assertEqual(created.first_name, "Erika")
        self.assertEqual(created.last_name, "Musterfrau")

        # Verify logging was called
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        self.assertEqual(call_args[0][0], self.admin)
        self.assertEqual(call_args[0][1], "patient_created")
        self.assertEqual(call_args[1]["patient_id"], 2001)

    @patch("praxi_backend.patients.views.log_patient_action")
    def test_create_as_doctor_success(self, mock_log):
        """Doctor can create a patient."""
        client = self._client_for(self.doctor)
        data = {
            "patient_id": 2002,
            "first_name": "Hans",
            "last_name": "Schmidt",
            "birth_date": "1975-07-10",
        }

        response = client.post("/api/patients/", data, format="json")

        self.assertEqual(response.status_code, 201)
        mock_log.assert_called_once()

    @patch("praxi_backend.patients.views.log_patient_action")
    def test_create_as_assistant_success(self, mock_log):
        """Assistant can create a patient."""
        client = self._client_for(self.assistant)
        data = {
            "patient_id": 2003,
            "first_name": "Test",
            "last_name": "User",
            "birth_date": "2000-01-01",
        }

        response = client.post("/api/patients/", data, format="json")

        self.assertEqual(response.status_code, 201)
        mock_log.assert_called_once()

    def test_create_as_billing_forbidden(self):
        """Billing cannot create patients (read-only)."""
        client = self._client_for(self.billing)
        data = {
            "patient_id": 2004,
            "first_name": "Test",
            "last_name": "User",
            "birth_date": "2000-01-01",
        }

        response = client.post("/api/patients/", data, format="json")

        self.assertEqual(response.status_code, 403)

    def test_create_invalid_patient_id(self):
        """Invalid patient_id returns validation error."""
        client = self._client_for(self.admin)
        data = {
            "patient_id": -1,
            "first_name": "Invalid",
            "last_name": "Patient",
            "birth_date": "2000-01-01",
        }

        response = client.post("/api/patients/", data, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("patient_id", response.data)

    # ========== RETRIEVE TESTS ==========

    def test_retrieve_as_admin_success(self):
        """Admin can retrieve a patient."""
        client = self._client_for(self.admin)
        response = client.get(f"/api/patients/{self.patient.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["patient_id"], 1001)
        self.assertEqual(response.data["first_name"], "Max")

    def test_retrieve_as_billing_success(self):
        """Billing can retrieve a patient (read-only)."""
        client = self._client_for(self.billing)
        response = client.get(f"/api/patients/{self.patient.pk}/")

        self.assertEqual(response.status_code, 200)

    def test_retrieve_not_found(self):
        """Non-existent patient returns 404."""
        client = self._client_for(self.admin)
        response = client.get("/api/patients/99999/")

        self.assertEqual(response.status_code, 404)

    # ========== UPDATE TESTS ==========

    @patch("praxi_backend.patients.views.log_patient_action")
    def test_update_as_admin_success(self, mock_log):
        """Admin can update a patient."""
        client = self._client_for(self.admin)
        data = {
            "patient_id": 1001,
            "first_name": "Maximilian",
            "last_name": "Mustermann",
            "birth_date": "1990-05-15",
        }

        response = client.put(f"/api/patients/{self.patient.pk}/", data, format="json")

        self.assertEqual(response.status_code, 200)

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.first_name, "Maximilian")

        # Verify logging was called
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        self.assertEqual(call_args[0][1], "patient_updated")

    @patch("praxi_backend.patients.views.log_patient_action")
    def test_partial_update_as_doctor_success(self, mock_log):
        """Doctor can partially update a patient."""
        client = self._client_for(self.doctor)
        data = {"first_name": "Maxi"}

        response = client.patch(f"/api/patients/{self.patient.pk}/", data, format="json")

        self.assertEqual(response.status_code, 200)

        self.patient.refresh_from_db()
        self.assertEqual(self.patient.first_name, "Maxi")

        mock_log.assert_called_once()

    def test_update_as_billing_forbidden(self):
        """Billing cannot update patients (read-only)."""
        client = self._client_for(self.billing)
        data = {"first_name": "Should Fail"}

        response = client.patch(f"/api/patients/{self.patient.pk}/", data, format="json")

        self.assertEqual(response.status_code, 403)

    # ========== RBAC SUMMARY TESTS ==========

    def test_rbac_read_roles(self):
        """Verify read access for allowed roles."""
        for user in [self.admin, self.assistant, self.doctor, self.billing]:
            client = self._client_for(user)
            response = client.get("/api/patients/")
            self.assertEqual(
                response.status_code,
                200,
                f"{user.role.name} should have read access",
            )

    def test_rbac_write_roles(self):
        """Verify write access for admin, assistant, doctor; denied for billing."""
        data = {
            "patient_id": 9999,
            "first_name": "RBAC",
            "last_name": "Test",
            "birth_date": "2000-01-01",
        }

        # Admin can write
        client = self._client_for(self.admin)
        response = client.post("/api/patients/", data, format="json")
        self.assertEqual(response.status_code, 201)

        # Assistant can write
        data["patient_id"] = 9998
        client = self._client_for(self.assistant)
        response = client.post("/api/patients/", data, format="json")
        self.assertEqual(response.status_code, 201)

        # Doctor can write
        data["patient_id"] = 9997
        client = self._client_for(self.doctor)
        response = client.post("/api/patients/", data, format="json")
        self.assertEqual(response.status_code, 201)

        # Billing cannot write (read-only)
        data["patient_id"] = 9996
        client = self._client_for(self.billing)
        response = client.post("/api/patients/", data, format="json")
        self.assertEqual(response.status_code, 403)
