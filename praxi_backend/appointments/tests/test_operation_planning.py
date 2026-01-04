from __future__ import annotations

from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import PracticeHours, DoctorHours, Resource, OperationType
from praxi_backend.core.models import AuditLog, Role, User


class OperationPlanningMiniTest(TestCase):
    """Mini-Test: OP-Planung (OperationType/Operation) inkl. Konflikte + Suggest + Kalender.

    Szenario:
    - OP-Raum (Resource type=room)
    - OP-Gerät (Resource type=device)
    - OP-Typ total 50 min (10+30+10)
    - OP A 10:00-10:50 belegt OP-Raum
    - OP B 10:30-... versucht selben Raum -> 400 "Operation conflict"
    - Suggest liefert 10:50-11:40

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
            username="admin_operation_test",
            email="admin_operation_test@example.com",
            password="DummyPass123!",
            role=role_admin,
        )
        self.doctor_a = User.objects.db_manager("default").create_user(
            username="doctor_operation_a",
            email="doctor_operation_a@example.com",
            password="DummyPass123!",
            role=role_doctor,
            first_name="Dr",
            last_name="A",
        )
        self.doctor_b = User.objects.db_manager("default").create_user(
            username="doctor_operation_b",
            email="doctor_operation_b@example.com",
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

        self.op_room = Resource.objects.using("default").create(
            name="OP 1",
            type="room",
            active=True,
        )
        self.device = Resource.objects.using("default").create(
            name="C-Bogen",
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

    def _iso_z(self, dt: datetime) -> str:
        return dt.isoformat().replace("+00:00", "Z")

    def test_operation_conflict_suggest_and_calendar(self):
        tz = timezone.get_current_timezone()

        start_a = timezone.make_aware(datetime.combine(self.monday, time(10, 0)), tz)
        payload_a = {
            "patient_id": self.patient_id,
            "primary_surgeon": self.doctor_a.id,
            "assistant": None,
            "anesthesist": None,
            "op_room": self.op_room.id,
            "op_device_ids": [self.device.id],
            "op_type": self.op_type.id,
            "start_time": self._iso_z(start_a),
            "status": "planned",
            "notes": "OP_A",
        }

        # 1) OP A erstellen
        r_a = self.client.post("/api/operations/", payload_a, format="json")
        self.assertEqual(r_a.status_code, 201)
        self.assertIn("T10:50:00", r_a.data.get("end_time", ""))

        # 2) OP B überlappt Raum -> 400 Operation conflict
        start_b = timezone.make_aware(datetime.combine(self.monday, time(10, 30)), tz)
        payload_b = {
            **payload_a,
            "primary_surgeon": self.doctor_b.id,
            "start_time": self._iso_z(start_b),
            "notes": "OP_B",
        }

        before_audit = AuditLog.objects.using("default").count()
        r_b = self.client.post("/api/operations/", payload_b, format="json")
        self.assertEqual(r_b.status_code, 400)
        self.assertIn("Operation conflict", str(r_b.data))

        after_audit = AuditLog.objects.using("default").count()
        self.assertGreaterEqual(after_audit, before_audit + 1)
        last = AuditLog.objects.using("default").order_by("-id").first()
        self.assertIsNotNone(last)
        self.assertEqual(last.action, "operation_conflict")

        # 3) Suggest: muss 10:50-11:40 liefern
        r_sug = self.client.get(
            "/api/operations/suggest/",
            {
                "patient_id": self.patient_id,
                "primary_surgeon_id": self.doctor_b.id,
                "op_type_id": self.op_type.id,
                "op_room_id": self.op_room.id,
                "op_device_ids": str(self.device.id),
                "start_date": self.monday.isoformat(),
                "limit": 1,
            },
        )
        self.assertEqual(r_sug.status_code, 200)
        suggestions = r_sug.data.get("suggestions") or []
        self.assertEqual(len(suggestions), 1)
        s = suggestions[0]
        self.assertIn("T10:50:00", s["start_time"])
        self.assertIn("T11:40:00", s["end_time"])

        # 4) Kalender enthält operations
        r_cal = self.client.get("/api/calendar/day/", {"date": self.monday.isoformat()})
        self.assertEqual(r_cal.status_code, 200)
        self.assertIn("operations", r_cal.data)
        ops = r_cal.data.get("operations") or []
        self.assertGreaterEqual(len(ops), 1)
