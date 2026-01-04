from __future__ import annotations

from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from praxi_backend.appointments.models import DoctorHours, PracticeHours
from praxi_backend.appointments.serializers import AppointmentCreateUpdateSerializer
from praxi_backend.core.models import Role, User


class AppointmentWorkingHoursMiniTests(TestCase):
    """Mini-Test für Arbeitszeiten-Konfliktprüfung.

    - PracticeHours Mo 08:00–16:00
    - DoctorHours Mo 09:00–12:00
    - Termin Mo 10:00–11:00 -> OK
    - Termin Mo 07:00–08:00 -> 400 (outside practice hours)
    - Termin Mo 13:00–14:00 -> 400 (outside doctor hours)

    Verwendet nur die default/system Test-DB.
    patient_id wird als Integer verwendet (keine FK zur medical DB).
    """

    databases = {"default"}

    def _next_monday_date(self):
        # pick a deterministic upcoming Monday (could be today if it's Monday)
        base = timezone.localdate()
        delta_days = (0 - base.weekday()) % 7
        return base + timedelta(days=delta_days)

    def _dt(self, day, hh, mm):
        naive = datetime.combine(day, time(hh, mm))
        return timezone.make_aware(naive, timezone.get_current_timezone())

    def test_working_hours_validation(self):
        # patient_id ist ein Integer, keine FK zur medical DB
        patient_id = 99999

        role_doctor, _ = Role.objects.using("default").get_or_create(
            name="doctor",
            defaults={"label": "Arzt"},
        )
        doctor = User.objects.db_manager("default").create_user(
            username="doctor_hours_test",
            email="doctor_hours_test@example.com",
            password="DummyPass123!",
            role=role_doctor,
        )

        # Monday windows
        PracticeHours.objects.using("default").create(
            weekday=0,
            start_time=time(8, 0),
            end_time=time(16, 0),
            active=True,
        )
        DoctorHours.objects.using("default").create(
            doctor=doctor,
            weekday=0,
            start_time=time(9, 0),
            end_time=time(12, 0),
            active=True,
        )

        monday = self._next_monday_date()

        # OK: 10:00-11:00
        ser_ok = AppointmentCreateUpdateSerializer(
            data={
                "patient_id": patient_id,
                "doctor": doctor.id,
                "start_time": self._dt(monday, 10, 0),
                "end_time": self._dt(monday, 11, 0),
                "status": "scheduled",
                "notes": "TEST",
            },
        )
        self.assertTrue(ser_ok.is_valid(), ser_ok.errors)

        # Outside practice: 07:00-08:00
        ser_practice_bad = AppointmentCreateUpdateSerializer(
            data={
                "patient_id": patient_id,
                "doctor": doctor.id,
                "start_time": self._dt(monday, 7, 0),
                "end_time": self._dt(monday, 8, 0),
                "status": "scheduled",
            },
        )
        self.assertFalse(ser_practice_bad.is_valid())
        self.assertEqual(ser_practice_bad.errors.get("detail"), ["Doctor unavailable."])
        self.assertEqual(ser_practice_bad.errors.get("alternatives"), [])

        # Outside doctor: 13:00-14:00 (inside practice)
        ser_doctor_bad = AppointmentCreateUpdateSerializer(
            data={
                "patient_id": patient_id,
                "doctor": doctor.id,
                "start_time": self._dt(monday, 13, 0),
                "end_time": self._dt(monday, 14, 0),
                "status": "scheduled",
            },
        )
        self.assertFalse(ser_doctor_bad.is_valid())
        self.assertEqual(ser_doctor_bad.errors.get("detail"), ["Doctor unavailable."])
        self.assertEqual(ser_doctor_bad.errors.get("alternatives"), [])
