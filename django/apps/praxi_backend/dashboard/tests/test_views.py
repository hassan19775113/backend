from __future__ import annotations

from django.test import RequestFactory, TestCase
from praxi_backend.appointments.models import Resource
from praxi_backend.core.models import User
from praxi_backend.dashboard.patient_views import PatientDashboardView, PatientOverviewView
from praxi_backend.dashboard.resources_views import ResourcesDashboardView
from praxi_backend.patients.models import Patient


class DashboardViewsSmokeTest(TestCase):
    """Smoke tests ensuring modernized dashboard views still render."""

    databases = {"default"}

    def setUp(self):
        self.rf = RequestFactory()
        self.staff_user = User.objects.db_manager("default").create_user(
            username="test_staff_dashboard_views",
            email="test_staff_dashboard_views@example.com",
            password="DummyPass123!",
            is_staff=True,
            is_active=True,
        )
        Patient.objects.using("default").create(id=1, first_name="Max", last_name="Mustermann")
        Resource.objects.using("default").create(
            name="Raum 1",
            type=Resource.TYPE_ROOM,
            color="#4A90E2",
            active=True,
        )

    def test_patient_overview_renders(self):
        request = self.rf.get("/dashboard/patients/overview/")
        request.user = self.staff_user
        response = PatientOverviewView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)

    def test_patient_detail_renders(self):
        request = self.rf.get("/dashboard/patients/", {"patient_id": "1"})
        request.user = self.staff_user
        response = PatientDashboardView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)

    def test_resources_dashboard_renders(self):
        request = self.rf.get("/dashboard/resources/")
        request.user = self.staff_user
        response = ResourcesDashboardView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
