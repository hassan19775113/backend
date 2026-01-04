from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import DoctorHours, PracticeHours
from praxi_backend.core.models import Role, User


class AppointmentConflictIntegrationTests(TestCase):
    """Integrationstest für Overlap-Detection.

    Verwendet nur die default/system Test-DB.
    patient_id wird als Integer verwendet (keine FK zur medical DB).
    """

    databases = {"default"}

    def test_conflict_flow(self):
        # patient_id ist ein Integer, keine FK zur medical DB
        patient_id = 99999

        role_admin, _ = Role.objects.using("default").get_or_create(
            name="admin",
            defaults={"label": "Administrator"},
        )
        role_doctor, _ = Role.objects.using("default").get_or_create(
            name="doctor",
            defaults={"label": "Arzt"},
        )

        admin = User.objects.db_manager("default").create_user(
            username="admin_conflict_test",
            email="admin_conflict_test@example.com",
            password="DummyPass123!",
            role=role_admin,
        )
        doctor1 = User.objects.db_manager("default").create_user(
            username="doctor_conflict_test",
            email="doctor_conflict_test@example.com",
            password="DummyPass123!",
            role=role_doctor,
        )

        client = APIClient()
        client.defaults["HTTP_HOST"] = "localhost"
        client.force_authenticate(user=admin)

        # Ensure working-hours validation does not block this conflict scenario.
        for weekday in range(7):
            PracticeHours.objects.using("default").create(
                weekday=weekday,
                start_time=timezone.datetime(2000, 1, 1, 8, 0).time(),
                end_time=timezone.datetime(2000, 1, 1, 18, 0).time(),
                active=True,
            )
            DoctorHours.objects.using("default").create(
                doctor=doctor1,
                weekday=weekday,
                start_time=timezone.datetime(2000, 1, 1, 8, 0).time(),
                end_time=timezone.datetime(2000, 1, 1, 18, 0).time(),
                active=True,
            )

        base = timezone.now() + timedelta(days=3)
        # Set time to 10:00 to ensure it's within working hours (8:00-18:00)
        a_start = base.replace(hour=10, minute=0, second=0, microsecond=0)
        a_end = a_start + timedelta(minutes=30)

        payload_a = {
            "patient_id": patient_id,
            "doctor": doctor1.id,
            "start_time": a_start.isoformat().replace("+00:00", "Z"),
            "end_time": a_end.isoformat().replace("+00:00", "Z"),
            "status": "scheduled",
            "notes": "TEST",
        }

        # 1) Termin A erstellen → 201
        r_a = client.post("/api/appointments/", payload_a, format="json")
        self.assertEqual(r_a.status_code, 201)
        appt_a_id = r_a.data.get("id")
        self.assertIsNotNone(appt_a_id)

        # 2) Termin B im freien Slot → 201
        b_start = a_start + timedelta(hours=2)
        b_end = b_start + timedelta(minutes=30)
        payload_b_free = {
            **payload_a,
            "start_time": b_start.isoformat().replace("+00:00", "Z"),
            "end_time": b_end.isoformat().replace("+00:00", "Z"),
        }

        r_b = client.post("/api/appointments/", payload_b_free, format="json")
        self.assertEqual(r_b.status_code, 201)
        appt_b_id = r_b.data.get("id")
        self.assertIsNotNone(appt_b_id)

        # 3) Termin B in A-Zeitfenster verschieben → 400
        payload_b_overlap = {
            **payload_b_free,
            "start_time": payload_a["start_time"],
            "end_time": payload_a["end_time"],
        }

        r_b_overlap = client.put(
            f"/api/appointments/{appt_b_id}/",
            payload_b_overlap,
            format="json",
        )
        self.assertEqual(r_b_overlap.status_code, 400)
        self.assertIn("detail", r_b_overlap.data)
        detail = r_b_overlap.data.get("detail")
        if isinstance(detail, list) and detail:
            detail = str(detail[0])
        else:
            detail = str(detail)
        self.assertEqual(detail, "Doctor unavailable.")
        self.assertIn("alternatives", r_b_overlap.data)

        # 4) Termin B in freien Slot verschieben → 200
        b2_start = a_start + timedelta(hours=4)
        b2_end = b2_start + timedelta(minutes=30)
        payload_b_free2 = {
            **payload_b_free,
            "start_time": b2_start.isoformat().replace("+00:00", "Z"),
            "end_time": b2_end.isoformat().replace("+00:00", "Z"),
        }

        r_b_free2 = client.put(
            f"/api/appointments/{appt_b_id}/",
            payload_b_free2,
            format="json",
        )
        self.assertEqual(r_b_free2.status_code, 200)
        self.assertEqual(r_b_free2.data.get("id"), appt_b_id)