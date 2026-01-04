from __future__ import annotations

from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import PracticeHours, DoctorHours, Resource
from praxi_backend.core.models import AuditLog, Role, User


class ResourcePlanningMiniTest(TestCase):
    """Mini-Test: Ressourcenplanung (Räume/Geräte) inkl. Suggest.

    - Resource "Ultraschallraum"
    - Termin A 10:00–10:30 nutzt Ultraschallraum
    - Termin B 10:15–10:45 versucht denselben Raum -> 400 "Resource conflict"
    - Suggest (30 min) liefert 10:30–11:00

    Verwendet nur die default/system Test-DB.
    patient_id wird als Integer verwendet (keine FK zur medical DB).
    """

    databases = {"default"}

    def setUp(self):
        # patient_id ist ein Integer, keine FK zur medical DB
        self.patient_id = 99999

        role_admin, _ = Role.objects.using("default").get_or_create(
            name="admin",
            defaults={"label": "Administrator"},
        )
        role_doctor, _ = Role.objects.using("default").get_or_create(
            name="doctor",
            defaults={"label": "Arzt"},
        )

        self.admin = User.objects.db_manager("default").create_user(
            username="admin_resource_test",
            email="admin_resource_test@example.com",
            password="DummyPass123!",
            role=role_admin,
        )
        self.doctor_a = User.objects.db_manager("default").create_user(
            username="doctor_resource_a",
            email="doctor_resource_a@example.com",
            password="DummyPass123!",
            role=role_doctor,
            first_name="Dr",
            last_name="A",
        )
        self.doctor_b = User.objects.db_manager("default").create_user(
            username="doctor_resource_b",
            email="doctor_resource_b@example.com",
            password="DummyPass123!",
            role=role_doctor,
            first_name="Dr",
            last_name="B",
        )

        self.client = APIClient()
        self.client.defaults["HTTP_HOST"] = "localhost"
        self.client.force_authenticate(user=self.admin)

        # Pick a deterministic Monday in the near future.
        base = timezone.localdate() + timedelta(days=7)
        self.monday = base - timedelta(days=base.weekday())
        weekday = self.monday.weekday()
        self.assertEqual(weekday, 0)

        PracticeHours.objects.using("default").create(
            weekday=weekday,
            start_time=time(10, 0),
            end_time=time(12, 0),
            active=True,
        )
        DoctorHours.objects.using("default").create(
            doctor=self.doctor_a,
            weekday=weekday,
            start_time=time(10, 0),
            end_time=time(12, 0),
            active=True,
        )
        DoctorHours.objects.using("default").create(
            doctor=self.doctor_b,
            weekday=weekday,
            start_time=time(10, 0),
            end_time=time(12, 0),
            active=True,
        )

        self.resource = Resource.objects.using("default").create(
            name="Ultraschallraum",
            type="room",
            active=True,
        )

    def _iso_z(self, dt: datetime) -> str:
        return dt.isoformat().replace("+00:00", "Z")

    def test_resource_conflict_and_suggest(self):
        tz = timezone.get_current_timezone()
        start_a = timezone.make_aware(datetime.combine(self.monday, time(10, 0)), tz)
        end_a = start_a + timedelta(minutes=30)

        payload_a = {
            "patient_id": self.patient_id,
            "doctor": self.doctor_a.id,
            "start_time": self._iso_z(start_a),
            "end_time": self._iso_z(end_a),
            "status": "scheduled",
            "notes": "RES_A",
            "resource_ids": [self.resource.id],
        }

        # 1) Termin A erstellen
        r_a = self.client.post("/api/appointments/", payload_a, format="json")
        self.assertEqual(r_a.status_code, 201)

        # 2) Termin B überlappt Ressource -> 400 Resource conflict
        start_b = timezone.make_aware(datetime.combine(self.monday, time(10, 15)), tz)
        end_b = timezone.make_aware(datetime.combine(self.monday, time(10, 45)), tz)
        payload_b = {
            **payload_a,
            "doctor": self.doctor_b.id,
            "start_time": self._iso_z(start_b),
            "end_time": self._iso_z(end_b),
            "notes": "RES_B",
        }

        before_audit = AuditLog.objects.using("default").count()
        r_b = self.client.post("/api/appointments/", payload_b, format="json")
        self.assertEqual(r_b.status_code, 400)
        self.assertIn("Resource conflict", str(r_b.data))

        after_audit = AuditLog.objects.using("default").count()
        self.assertGreaterEqual(after_audit, before_audit + 1)
        last = AuditLog.objects.using("default").order_by("-id").first()
        self.assertIsNotNone(last)
        self.assertEqual(last.action, "resource_booking_conflict")

        # 3) Suggest: muss 10:30-11:00 liefern
        r_sug = self.client.get(
            "/api/appointments/suggest/",
            {
                "doctor_id": self.doctor_b.id,
                "duration_minutes": 30,
                "start_date": self.monday.isoformat(),
                "limit": 1,
                "resource_ids": str(self.resource.id),
            },
        )
        self.assertEqual(r_sug.status_code, 200)
        self.assertEqual(len(r_sug.data.get("primary_suggestions") or []), 1)
        s = r_sug.data["primary_suggestions"][0]
        self.assertIn("T10:30:00", s["start_time"])
        self.assertIn("T11:00:00", s["end_time"])
        self.assertEqual(s.get("resource_ids"), [self.resource.id])
        self.assertEqual(s.get("resource_colors"), [self.resource.color])
