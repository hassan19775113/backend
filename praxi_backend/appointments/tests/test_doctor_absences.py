from __future__ import annotations

from datetime import date, datetime, time

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from praxi_backend.appointments.models import DoctorHours, PracticeHours
from praxi_backend.core.models import Role, User


class DoctorAbsenceAppointmentCalendarMiniTests(TestCase):
    """Mini-Test:
    - DoctorAbsence 10.–20. Januar
    - Termin 15. Januar -> 400
    - Termin 21. Januar -> 201
    - Kalender-Week-View für 13.–19. Januar enthält die Abwesenheit

    Verwendet nur die default/system Test-DB.
    patient_id wird als Integer verwendet (keine FK zur medical DB).
    """

    databases = {"default"}

    def _client_for(self, user: User) -> APIClient:
        client = APIClient()
        client.defaults["HTTP_HOST"] = "localhost"
        client.force_authenticate(user=user)
        return client

    def _iso_z(self, dt: datetime) -> str:
        val = dt.isoformat()
        return val.replace("+00:00", "Z")

    def _aware(self, d: date, hh: int, mm: int) -> datetime:
        naive = datetime.combine(d, time(hh, mm))
        return timezone.make_aware(naive, timezone.get_current_timezone())

    def setUp(self):
        role_admin, _ = Role.objects.using("default").get_or_create(
            name="admin",
            defaults={"label": "Administrator"},
        )
        role_doctor, _ = Role.objects.using("default").get_or_create(
            name="doctor",
            defaults={"label": "Arzt"},
        )

        self.admin = User.objects.db_manager("default").create_user(
            username="admin_abs_test",
            email="admin_abs_test@example.com",
            password="DummyPass123!",
            role=role_admin,
        )
        self.doctor = User.objects.db_manager("default").create_user(
            username="doctor_abs_test",
            email="doctor_abs_test@example.com",
            password="DummyPass123!",
            role=role_doctor,
        )

        # Ensure working-hours checks won't block the appointments in this test.
        for weekday in range(7):
            PracticeHours.objects.using("default").create(
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(16, 0),
                active=True,
            )
            DoctorHours.objects.using("default").create(
                doctor=self.doctor,
                weekday=weekday,
                start_time=time(9, 0),
                end_time=time(12, 0),
                active=True,
            )

        self.client = self._client_for(self.admin)

    def test_absence_blocks_appointments_and_calendar_includes_absence(self):
        # patient_id ist ein Integer, keine FK zur medical DB
        patient_id = 99999

        # Use a fixed January window (year explicit)
        absence_start = date(2026, 1, 10)
        absence_end = date(2026, 1, 20)

        # Create absence 10-20 Jan
        r_abs = self.client.post(
            "/api/doctor-absences/",
            {
                "doctor": self.doctor.id,
                "start_date": absence_start.isoformat(),
                "end_date": absence_end.isoformat(),
                "reason": "Urlaub",
                "active": True,
            },
            format="json",
        )
        self.assertEqual(r_abs.status_code, 201)
        absence_id = r_abs.data.get("id")
        self.assertIsNotNone(absence_id)

        # Appointment during absence: 15 Jan -> 400
        day_in = date(2026, 1, 15)
        start_in = self._aware(day_in, 10, 0)
        end_in = self._aware(day_in, 11, 0)
        r_in = self.client.post(
            "/api/appointments/",
            {
                "patient_id": patient_id,
                "doctor": self.doctor.id,
                "start_time": self._iso_z(start_in),
                "end_time": self._iso_z(end_in),
                "status": "scheduled",
                "notes": "ABSENCE_BLOCK",
            },
            format="json",
        )
        self.assertEqual(r_in.status_code, 400)
        self.assertEqual(r_in.data.get("detail"), ["Doctor unavailable."])
        self.assertIn("alternatives", r_in.data)

        # Appointment after absence: 21 Jan -> 201
        day_out = date(2026, 1, 21)
        start_out = self._aware(day_out, 10, 0)
        end_out = self._aware(day_out, 11, 0)
        r_out = self.client.post(
            "/api/appointments/",
            {
                "patient_id": patient_id,
                "doctor": self.doctor.id,
                "start_time": self._iso_z(start_out),
                "end_time": self._iso_z(end_out),
                "status": "scheduled",
                "notes": "ABSENCE_OK",
            },
            format="json",
        )
        self.assertEqual(r_out.status_code, 201)

        # Calendar week containing 13-19 Jan should include absence
        # Pick date within that week: 2026-01-15
        r_week = self.client.get(f"/api/calendar/week/?date=2026-01-15&doctor_id={self.doctor.id}")
        self.assertEqual(r_week.status_code, 200)
        absences = (r_week.data or {}).get("absences", [])
        self.assertGreaterEqual(len(absences), 1)
        found = [a for a in absences if a.get("id") == absence_id]
        self.assertTrue(found)
        self.assertEqual(found[0].get("start_date"), absence_start.isoformat())
        self.assertEqual(found[0].get("end_date"), absence_end.isoformat())
