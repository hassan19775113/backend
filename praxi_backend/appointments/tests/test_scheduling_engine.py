"""
Comprehensive tests for the Scheduling Engine.

Tests cover:
- Conflict detection (doctor, room, device, patient)
- Working hours validation
- Doctor absence validation
- Doctor break validation
- Integration tests (View + Service)

All tests use only the default database and patient_id as integer.
No access to medical.Patient.
"""

from datetime import date, datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from praxi_backend.core.models import Role, User
from praxi_backend.appointments.models import (
    Appointment,
    AppointmentResource,
    AppointmentType,
    DoctorAbsence,
    DoctorBreak,
    DoctorHours,
    Operation,
    OperationDevice,
    OperationType,
    PracticeHours,
    Resource,
)
from praxi_backend.appointments.exceptions import (
    DoctorAbsentError,
    DoctorBreakConflict,
    InvalidSchedulingData,
    SchedulingConflictError,
    WorkingHoursViolation,
)
from praxi_backend.appointments.services.scheduling import (
    check_appointment_conflicts,
    check_operation_conflicts,
    check_patient_conflicts,
    plan_appointment,
    plan_operation,
    validate_doctor_absences,
    validate_doctor_breaks,
    validate_working_hours,
)


# Dummy patient_id for tests (no access to medical DB)
DUMMY_PATIENT_ID = 99999


class SchedulingTestMixin:
    """Mixin providing common setup for scheduling tests."""

    databases = {"default"}

    def setUp(self):
        super().setUp()
        # Create roles
        self.role_admin, _ = Role.objects.using("default").get_or_create(
            name="admin", defaults={"label": "Administrator"}
        )
        self.role_doctor, _ = Role.objects.using("default").get_or_create(
            name="doctor", defaults={"label": "Arzt"}
        )
        self.role_assistant, _ = Role.objects.using("default").get_or_create(
            name="assistant", defaults={"label": "Assistent"}
        )

        # Create admin user
        self.admin = User.objects.db_manager("default").create_user(
            username="admin_sched",
            password="admin123",
            email="admin_sched@test.local",
            role=self.role_admin,
        )

        # Create doctors
        self.doctor1 = User.objects.db_manager("default").create_user(
            username="doctor1_sched",
            password="doc123",
            email="doctor1_sched@test.local",
            role=self.role_doctor,
        )
        self.doctor2 = User.objects.db_manager("default").create_user(
            username="doctor2_sched",
            password="doc123",
            email="doctor2_sched@test.local",
            role=self.role_doctor,
        )

        # Create appointment type
        self.appt_type = AppointmentType.objects.using("default").create(
            name="Test Checkup",
            color="#2E8B57",
            duration_minutes=30,
            active=True,
        )

        # Create operation type
        self.op_type = OperationType.objects.using("default").create(
            name="Test Surgery",
            prep_duration=15,
            op_duration=60,
            post_duration=15,
            color="#8A2BE2",
            active=True,
        )

        # Create resources
        self.room1 = Resource.objects.using("default").create(
            name="Room 1",
            type="room",
            color="#6A5ACD",
            active=True,
        )
        self.room2 = Resource.objects.using("default").create(
            name="Room 2",
            type="room",
            color="#4169E1",
            active=True,
        )
        self.device1 = Resource.objects.using("default").create(
            name="Device 1",
            type="device",
            color="#228B22",
            active=True,
        )

        # Set up timezone and dates
        self.tz = timezone.get_current_timezone()
        self.today = timezone.localdate()
        self.tomorrow = self.today + timedelta(days=1)

        # Create practice hours (Mon-Fri, 08:00-18:00)
        for weekday in range(5):  # 0=Mon to 4=Fri
            PracticeHours.objects.using("default").create(
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(18, 0),
                active=True,
            )

        # Create doctor hours for doctor1 (Mon-Fri, 08:00-18:00)
        for weekday in range(5):
            DoctorHours.objects.using("default").create(
                doctor=self.doctor1,
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(18, 0),
                active=True,
            )

        # Create doctor hours for doctor2 (Mon-Fri, 09:00-17:00)
        for weekday in range(5):
            DoctorHours.objects.using("default").create(
                doctor=self.doctor2,
                weekday=weekday,
                start_time=time(9, 0),
                end_time=time(17, 0),
                active=True,
            )

    def _make_datetime(self, d: date, t: time) -> datetime:
        """Create a timezone-aware datetime."""
        return timezone.make_aware(datetime.combine(d, t), self.tz)

    def _get_next_weekday(self, start_date: date, target_weekday: int) -> date:
        """Get the next occurrence of a weekday (0=Mon) from start_date."""
        days_ahead = target_weekday - start_date.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return start_date + timedelta(days=days_ahead)


# =============================================================================
# Conflict Detection Tests
# =============================================================================


class CheckAppointmentConflictsTestCase(SchedulingTestMixin, TestCase):
    """Tests for check_appointment_conflicts function."""

    def test_no_conflicts_empty_schedule(self):
        """No conflicts when schedule is empty."""
        monday = self._get_next_weekday(self.today, 0)
        start = self._make_datetime(monday, time(10, 0))
        end = self._make_datetime(monday, time(10, 30))

        conflicts = check_appointment_conflicts(
            date=monday,
            start_time=start,
            end_time=end,
            doctor_id=self.doctor1.id,
        )

        self.assertEqual(conflicts, [])

    def test_doctor_conflict_with_appointment(self):
        """Detect conflict when doctor has overlapping appointment."""
        monday = self._get_next_weekday(self.today, 0)
        
        # Create existing appointment
        existing = Appointment.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID,
            doctor=self.doctor1,
            type=self.appt_type,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(10, 30)),
            status="scheduled",
        )

        # Try to schedule overlapping appointment
        conflicts = check_appointment_conflicts(
            date=monday,
            start_time=self._make_datetime(monday, time(10, 15)),
            end_time=self._make_datetime(monday, time(10, 45)),
            doctor_id=self.doctor1.id,
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].type, "doctor_conflict")
        self.assertEqual(conflicts[0].model, "Appointment")
        self.assertEqual(conflicts[0].id, existing.id)

    def test_doctor_conflict_with_operation(self):
        """Detect conflict when doctor is involved in an operation."""
        monday = self._get_next_weekday(self.today, 0)
        
        # Create existing operation where doctor1 is primary surgeon
        Operation.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID,
            primary_surgeon=self.doctor1,
            op_room=self.room1,
            op_type=self.op_type,
            start_time=self._make_datetime(monday, time(11, 0)),
            end_time=self._make_datetime(monday, time(12, 30)),
            status="planned",
        )

        # Try to schedule overlapping appointment
        conflicts = check_appointment_conflicts(
            date=monday,
            start_time=self._make_datetime(monday, time(11, 30)),
            end_time=self._make_datetime(monday, time(12, 0)),
            doctor_id=self.doctor1.id,
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].type, "doctor_conflict")
        self.assertEqual(conflicts[0].model, "Operation")

    def test_room_conflict_with_appointment(self):
        """Detect room conflict when resource is booked by another appointment."""
        monday = self._get_next_weekday(self.today, 0)
        
        # Create existing appointment with room
        existing = Appointment.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID,
            doctor=self.doctor2,  # Different doctor
            type=self.appt_type,
            start_time=self._make_datetime(monday, time(14, 0)),
            end_time=self._make_datetime(monday, time(14, 30)),
            status="scheduled",
        )
        AppointmentResource.objects.using("default").create(
            appointment=existing,
            resource=self.room1,
        )

        # Try to schedule overlapping appointment with same room
        conflicts = check_appointment_conflicts(
            date=monday,
            start_time=self._make_datetime(monday, time(14, 15)),
            end_time=self._make_datetime(monday, time(14, 45)),
            doctor_id=self.doctor1.id,
            resource_ids=[self.room1.id],
        )

        # Should have room conflict (no doctor conflict since different doctor)
        room_conflicts = [c for c in conflicts if c.type == "room_conflict"]
        self.assertEqual(len(room_conflicts), 1)
        self.assertEqual(room_conflicts[0].resource_id, self.room1.id)

    def test_exclude_appointment_id(self):
        """Excluding appointment ID should not flag it as conflict."""
        monday = self._get_next_weekday(self.today, 0)
        
        # Create existing appointment
        existing = Appointment.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID,
            doctor=self.doctor1,
            type=self.appt_type,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(10, 30)),
            status="scheduled",
        )

        # Check with exclusion (simulating update)
        conflicts = check_appointment_conflicts(
            date=monday,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(10, 30)),
            doctor_id=self.doctor1.id,
            exclude_appointment_id=existing.id,
        )

        self.assertEqual(conflicts, [])


class CheckOperationConflictsTestCase(SchedulingTestMixin, TestCase):
    """Tests for check_operation_conflicts function."""

    def test_no_conflicts_empty_schedule(self):
        """No conflicts when schedule is empty."""
        monday = self._get_next_weekday(self.today, 0)
        start = self._make_datetime(monday, time(10, 0))
        end = self._make_datetime(monday, time(11, 30))

        conflicts = check_operation_conflicts(
            date=monday,
            start_time=start,
            end_time=end,
            primary_surgeon_id=self.doctor1.id,
            room_id=self.room1.id,
        )

        self.assertEqual(conflicts, [])

    def test_room_conflict_with_operation(self):
        """Detect room conflict with another operation."""
        monday = self._get_next_weekday(self.today, 0)
        
        # Create existing operation
        existing = Operation.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID,
            primary_surgeon=self.doctor2,  # Different surgeon
            op_room=self.room1,
            op_type=self.op_type,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(11, 30)),
            status="planned",
        )

        # Try to schedule overlapping operation in same room
        conflicts = check_operation_conflicts(
            date=monday,
            start_time=self._make_datetime(monday, time(11, 0)),
            end_time=self._make_datetime(monday, time(12, 30)),
            primary_surgeon_id=self.doctor1.id,
            room_id=self.room1.id,
        )

        room_conflicts = [c for c in conflicts if c.type == "room_conflict"]
        self.assertEqual(len(room_conflicts), 1)
        self.assertEqual(room_conflicts[0].model, "Operation")
        self.assertEqual(room_conflicts[0].id, existing.id)

    def test_device_conflict(self):
        """Detect device conflict with another operation."""
        monday = self._get_next_weekday(self.today, 0)
        
        # Create existing operation with device
        existing = Operation.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID,
            primary_surgeon=self.doctor2,
            op_room=self.room2,  # Different room
            op_type=self.op_type,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(11, 30)),
            status="planned",
        )
        OperationDevice.objects.using("default").create(
            operation=existing,
            resource=self.device1,
        )

        # Try to schedule overlapping operation with same device
        conflicts = check_operation_conflicts(
            date=monday,
            start_time=self._make_datetime(monday, time(11, 0)),
            end_time=self._make_datetime(monday, time(12, 30)),
            primary_surgeon_id=self.doctor1.id,
            room_id=self.room1.id,  # Different room
            device_ids=[self.device1.id],  # Same device
        )

        device_conflicts = [c for c in conflicts if c.type == "device_conflict"]
        self.assertEqual(len(device_conflicts), 1)
        self.assertEqual(device_conflicts[0].resource_id, self.device1.id)

    def test_surgeon_conflict_with_appointment(self):
        """Detect surgeon conflict when they have an appointment."""
        monday = self._get_next_weekday(self.today, 0)
        
        # Create existing appointment for surgeon
        Appointment.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID,
            doctor=self.doctor1,
            type=self.appt_type,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(10, 30)),
            status="scheduled",
        )

        # Try to schedule overlapping operation
        conflicts = check_operation_conflicts(
            date=monday,
            start_time=self._make_datetime(monday, time(10, 15)),
            end_time=self._make_datetime(monday, time(11, 45)),
            primary_surgeon_id=self.doctor1.id,
            room_id=self.room1.id,
        )

        doctor_conflicts = [c for c in conflicts if c.type == "doctor_conflict"]
        self.assertGreaterEqual(len(doctor_conflicts), 1)


class CheckPatientConflictsTestCase(SchedulingTestMixin, TestCase):
    """Tests for check_patient_conflicts function."""

    def test_patient_conflict_with_appointment(self):
        """Detect conflict when patient already has an appointment."""
        monday = self._get_next_weekday(self.today, 0)
        
        Appointment.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID,
            doctor=self.doctor1,
            type=self.appt_type,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(10, 30)),
            status="scheduled",
        )

        conflicts = check_patient_conflicts(
            patient_id=DUMMY_PATIENT_ID,
            start_time=self._make_datetime(monday, time(10, 15)),
            end_time=self._make_datetime(monday, time(10, 45)),
        )

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].type, "patient_conflict")
        self.assertEqual(conflicts[0].model, "Appointment")


# =============================================================================
# Working Hours Validation Tests
# =============================================================================


class ValidateWorkingHoursTestCase(SchedulingTestMixin, TestCase):
    """Tests for validate_working_hours function."""

    def test_valid_within_hours(self):
        """No error when appointment is within working hours."""
        monday = self._get_next_weekday(self.today, 0)

        # Should not raise
        validate_working_hours(
            date=monday,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(10, 30)),
            doctor_id=self.doctor1.id,
        )

    def test_no_practice_hours(self):
        """Error when no practice hours on that day."""
        # Get Sunday (no practice hours)
        sunday = self._get_next_weekday(self.today, 6)

        with self.assertRaises(WorkingHoursViolation) as ctx:
            validate_working_hours(
                date=sunday,
                start_time=self._make_datetime(sunday, time(10, 0)),
                end_time=self._make_datetime(sunday, time(10, 30)),
                doctor_id=self.doctor1.id,
            )

        self.assertEqual(ctx.exception.reason, "no_practice_hours")

    def test_outside_practice_hours(self):
        """Error when appointment is outside practice hours."""
        monday = self._get_next_weekday(self.today, 0)

        with self.assertRaises(WorkingHoursViolation) as ctx:
            validate_working_hours(
                date=monday,
                start_time=self._make_datetime(monday, time(7, 0)),  # Before 08:00
                end_time=self._make_datetime(monday, time(7, 30)),
                doctor_id=self.doctor1.id,
            )

        self.assertEqual(ctx.exception.reason, "outside_practice_hours")

    def test_no_doctor_hours(self):
        """Error when doctor has no hours on that day."""
        monday = self._get_next_weekday(self.today, 0)
        
        # Create a doctor without hours
        new_doctor = User.objects.db_manager("default").create_user(
            username="no_hours_doc",
            password="doc123",
            email="no_hours@test.local",
            role=self.role_doctor,
        )

        with self.assertRaises(WorkingHoursViolation) as ctx:
            validate_working_hours(
                date=monday,
                start_time=self._make_datetime(monday, time(10, 0)),
                end_time=self._make_datetime(monday, time(10, 30)),
                doctor_id=new_doctor.id,
            )

        self.assertEqual(ctx.exception.reason, "no_doctor_hours")

    def test_outside_doctor_hours(self):
        """Error when appointment is outside doctor's hours."""
        monday = self._get_next_weekday(self.today, 0)

        # doctor2 works 09:00-17:00
        with self.assertRaises(WorkingHoursViolation) as ctx:
            validate_working_hours(
                date=monday,
                start_time=self._make_datetime(monday, time(8, 0)),  # Before 09:00
                end_time=self._make_datetime(monday, time(8, 30)),
                doctor_id=self.doctor2.id,
            )

        self.assertEqual(ctx.exception.reason, "outside_doctor_hours")


# =============================================================================
# Doctor Absence Validation Tests
# =============================================================================


class ValidateDoctorAbsencesTestCase(SchedulingTestMixin, TestCase):
    """Tests for validate_doctor_absences function."""

    def test_no_absence(self):
        """No error when doctor is not absent."""
        monday = self._get_next_weekday(self.today, 0)

        # Should not raise
        validate_doctor_absences(
            date=monday,
            doctor_id=self.doctor1.id,
        )

    def test_doctor_absent(self):
        """Error when doctor is absent on the requested date."""
        monday = self._get_next_weekday(self.today, 0)
        
        # Create absence
        absence = DoctorAbsence.objects.using("default").create(
            doctor=self.doctor1,
            start_date=monday,
            end_date=monday + timedelta(days=7),
            reason="Vacation",
            active=True,
        )

        with self.assertRaises(DoctorAbsentError) as ctx:
            validate_doctor_absences(
                date=monday,
                doctor_id=self.doctor1.id,
            )

        self.assertEqual(ctx.exception.doctor_id, self.doctor1.id)
        self.assertEqual(ctx.exception.absence_id, absence.id)
        self.assertEqual(ctx.exception.reason, "Vacation")

    def test_inactive_absence_ignored(self):
        """Inactive absences should be ignored."""
        monday = self._get_next_weekday(self.today, 0)
        
        DoctorAbsence.objects.using("default").create(
            doctor=self.doctor1,
            start_date=monday,
            end_date=monday + timedelta(days=7),
            reason="Vacation",
            active=False,  # Inactive
        )

        # Should not raise
        validate_doctor_absences(
            date=monday,
            doctor_id=self.doctor1.id,
        )


# =============================================================================
# Doctor Break Validation Tests
# =============================================================================


class ValidateDoctorBreaksTestCase(SchedulingTestMixin, TestCase):
    """Tests for validate_doctor_breaks function."""

    def test_no_break_overlap(self):
        """No error when appointment doesn't overlap with breaks."""
        monday = self._get_next_weekday(self.today, 0)

        # Create a break
        DoctorBreak.objects.using("default").create(
            doctor=self.doctor1,
            date=monday,
            start_time=time(12, 0),
            end_time=time(13, 0),
            reason="Lunch",
            active=True,
        )

        # Should not raise - appointment is before break
        validate_doctor_breaks(
            date=monday,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(10, 30)),
            doctor_id=self.doctor1.id,
        )

    def test_break_overlap(self):
        """Error when appointment overlaps with a break."""
        monday = self._get_next_weekday(self.today, 0)

        DoctorBreak.objects.using("default").create(
            doctor=self.doctor1,
            date=monday,
            start_time=time(12, 0),
            end_time=time(13, 0),
            reason="Lunch",
            active=True,
        )

        with self.assertRaises(DoctorBreakConflict) as ctx:
            validate_doctor_breaks(
                date=monday,
                start_time=self._make_datetime(monday, time(12, 30)),
                end_time=self._make_datetime(monday, time(13, 30)),
                doctor_id=self.doctor1.id,
            )

        self.assertEqual(ctx.exception.doctor_id, self.doctor1.id)

    def test_practice_wide_break(self):
        """Practice-wide breaks (doctor=NULL) apply to all doctors."""
        monday = self._get_next_weekday(self.today, 0)

        # Practice-wide break
        DoctorBreak.objects.using("default").create(
            doctor=None,  # Practice-wide
            date=monday,
            start_time=time(12, 0),
            end_time=time(13, 0),
            reason="Team Meeting",
            active=True,
        )

        with self.assertRaises(DoctorBreakConflict):
            validate_doctor_breaks(
                date=monday,
                start_time=self._make_datetime(monday, time(12, 30)),
                end_time=self._make_datetime(monday, time(13, 30)),
                doctor_id=self.doctor1.id,
            )


# =============================================================================
# Plan Appointment Tests
# =============================================================================


class PlanAppointmentTestCase(SchedulingTestMixin, TestCase):
    """Tests for plan_appointment function."""

    def test_successful_appointment(self):
        """Successfully plan an appointment."""
        monday = self._get_next_weekday(self.today, 0)

        appointment = plan_appointment(
            data={
                "patient_id": DUMMY_PATIENT_ID,
                "doctor_id": self.doctor1.id,
                "start_time": self._make_datetime(monday, time(10, 0)),
                "end_time": self._make_datetime(monday, time(10, 30)),
                "type_id": self.appt_type.id,
            },
            user=self.admin,
        )

        self.assertIsNotNone(appointment.id)
        self.assertEqual(appointment.patient_id, DUMMY_PATIENT_ID)
        self.assertEqual(appointment.doctor_id, self.doctor1.id)
        self.assertEqual(appointment.status, "scheduled")

    def test_missing_required_fields(self):
        """Error when required fields are missing."""
        with self.assertRaises(InvalidSchedulingData) as ctx:
            plan_appointment(
                data={
                    "doctor_id": self.doctor1.id,
                    # Missing patient_id, start_time, end_time
                },
                user=self.admin,
            )

        self.assertEqual(ctx.exception.field, "patient_id")

    def test_doctor_conflict_raises_error(self):
        """SchedulingConflictError raised on doctor conflict."""
        monday = self._get_next_weekday(self.today, 0)

        # Create existing appointment
        Appointment.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID + 1,
            doctor=self.doctor1,
            type=self.appt_type,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(10, 30)),
            status="scheduled",
        )

        with self.assertRaises(SchedulingConflictError) as ctx:
            plan_appointment(
                data={
                    "patient_id": DUMMY_PATIENT_ID,
                    "doctor_id": self.doctor1.id,
                    "start_time": self._make_datetime(monday, time(10, 15)),
                    "end_time": self._make_datetime(monday, time(10, 45)),
                },
                user=self.admin,
            )

        conflicts = ctx.exception.conflicts
        doctor_conflicts = [c for c in conflicts if c.type == "doctor_conflict"]
        self.assertGreaterEqual(len(doctor_conflicts), 1)

    def test_working_hours_violation(self):
        """WorkingHoursViolation raised when outside working hours."""
        sunday = self._get_next_weekday(self.today, 6)

        with self.assertRaises(WorkingHoursViolation):
            plan_appointment(
                data={
                    "patient_id": DUMMY_PATIENT_ID,
                    "doctor_id": self.doctor1.id,
                    "start_time": self._make_datetime(sunday, time(10, 0)),
                    "end_time": self._make_datetime(sunday, time(10, 30)),
                },
                user=self.admin,
            )

    def test_doctor_absent_error(self):
        """DoctorAbsentError raised when doctor is absent."""
        monday = self._get_next_weekday(self.today, 0)

        DoctorAbsence.objects.using("default").create(
            doctor=self.doctor1,
            start_date=monday,
            end_date=monday + timedelta(days=7),
            reason="Vacation",
            active=True,
        )

        with self.assertRaises(DoctorAbsentError):
            plan_appointment(
                data={
                    "patient_id": DUMMY_PATIENT_ID,
                    "doctor_id": self.doctor1.id,
                    "start_time": self._make_datetime(monday, time(10, 0)),
                    "end_time": self._make_datetime(monday, time(10, 30)),
                },
                user=self.admin,
            )

    def test_appointment_with_resources(self):
        """Successfully plan appointment with resources."""
        monday = self._get_next_weekday(self.today, 0)

        appointment = plan_appointment(
            data={
                "patient_id": DUMMY_PATIENT_ID,
                "doctor_id": self.doctor1.id,
                "start_time": self._make_datetime(monday, time(10, 0)),
                "end_time": self._make_datetime(monday, time(10, 30)),
                "resource_ids": [self.room1.id, self.device1.id],
            },
            user=self.admin,
        )

        self.assertIsNotNone(appointment.id)
        resources = list(appointment.resources.all())
        self.assertEqual(len(resources), 2)


# =============================================================================
# Plan Operation Tests
# =============================================================================


class PlanOperationTestCase(SchedulingTestMixin, TestCase):
    """Tests for plan_operation function."""

    def test_successful_operation(self):
        """Successfully plan an operation."""
        monday = self._get_next_weekday(self.today, 0)

        operation = plan_operation(
            data={
                "patient_id": DUMMY_PATIENT_ID,
                "primary_surgeon_id": self.doctor1.id,
                "op_room_id": self.room1.id,
                "op_type_id": self.op_type.id,
                "start_time": self._make_datetime(monday, time(10, 0)),
            },
            user=self.admin,
        )

        self.assertIsNotNone(operation.id)
        self.assertEqual(operation.patient_id, DUMMY_PATIENT_ID)
        self.assertEqual(operation.primary_surgeon_id, self.doctor1.id)
        self.assertEqual(operation.status, "planned")

        # Check end_time is calculated from op_type
        expected_end = self._make_datetime(monday, time(10, 0)) + timedelta(minutes=90)
        self.assertEqual(operation.end_time, expected_end)

    def test_room_conflict_raises_error(self):
        """SchedulingConflictError raised on room conflict."""
        monday = self._get_next_weekday(self.today, 0)

        # Create existing operation
        Operation.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID + 1,
            primary_surgeon=self.doctor2,
            op_room=self.room1,
            op_type=self.op_type,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(11, 30)),
            status="planned",
        )

        with self.assertRaises(SchedulingConflictError) as ctx:
            plan_operation(
                data={
                    "patient_id": DUMMY_PATIENT_ID,
                    "primary_surgeon_id": self.doctor1.id,
                    "op_room_id": self.room1.id,
                    "op_type_id": self.op_type.id,
                    "start_time": self._make_datetime(monday, time(11, 0)),
                },
                user=self.admin,
            )

        conflicts = ctx.exception.conflicts
        room_conflicts = [c for c in conflicts if c.type == "room_conflict"]
        self.assertGreaterEqual(len(room_conflicts), 1)

    def test_operation_with_team(self):
        """Successfully plan operation with full team."""
        monday = self._get_next_weekday(self.today, 0)

        operation = plan_operation(
            data={
                "patient_id": DUMMY_PATIENT_ID,
                "primary_surgeon_id": self.doctor1.id,
                "assistant_id": self.doctor2.id,
                "op_room_id": self.room1.id,
                "op_type_id": self.op_type.id,
                "start_time": self._make_datetime(monday, time(10, 0)),
            },
            user=self.admin,
        )

        self.assertEqual(operation.primary_surgeon_id, self.doctor1.id)
        self.assertEqual(operation.assistant_id, self.doctor2.id)

    def test_operation_with_devices(self):
        """Successfully plan operation with devices."""
        monday = self._get_next_weekday(self.today, 0)

        operation = plan_operation(
            data={
                "patient_id": DUMMY_PATIENT_ID,
                "primary_surgeon_id": self.doctor1.id,
                "op_room_id": self.room1.id,
                "op_type_id": self.op_type.id,
                "start_time": self._make_datetime(monday, time(10, 0)),
                "op_device_ids": [self.device1.id],
            },
            user=self.admin,
        )

        devices = list(operation.op_devices.all())
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].id, self.device1.id)


# =============================================================================
# Integration Tests (View + Service)
# =============================================================================


class AppointmentViewIntegrationTestCase(SchedulingTestMixin, TestCase):
    """Integration tests for AppointmentListCreateView with scheduling service."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.url = "/api/appointments/"

    def test_create_appointment_success(self):
        """201 response for successful appointment creation."""
        monday = self._get_next_weekday(self.today, 0)

        response = self.client.post(
            self.url,
            {
                "patient_id": DUMMY_PATIENT_ID,
                "doctor": self.doctor1.id,
                "start_time": self._make_datetime(monday, time(10, 0)).isoformat(),
                "end_time": self._make_datetime(monday, time(10, 30)).isoformat(),
                "type": self.appt_type.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["patient_id"], DUMMY_PATIENT_ID)

    def test_create_appointment_conflict_400(self):
        """400 response when conflict is detected."""
        monday = self._get_next_weekday(self.today, 0)

        # Create existing appointment
        Appointment.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID + 1,
            doctor=self.doctor1,
            type=self.appt_type,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(10, 30)),
            status="scheduled",
        )

        response = self.client.post(
            self.url,
            {
                "patient_id": DUMMY_PATIENT_ID,
                "doctor": self.doctor1.id,
                "start_time": self._make_datetime(monday, time(10, 15)).isoformat(),
                "end_time": self._make_datetime(monday, time(10, 45)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # API returns either 'conflicts' (scheduling service) or 'detail' (serializer validation)
        self.assertTrue(
            "conflicts" in response.data or "detail" in response.data,
            f"Expected 'conflicts' or 'detail' in response, got: {response.data.keys()}"
        )

    def test_create_appointment_outside_hours_400(self):
        """400 response when appointment is outside working hours."""
        sunday = self._get_next_weekday(self.today, 6)

        response = self.client.post(
            self.url,
            {
                "patient_id": DUMMY_PATIENT_ID,
                "doctor": self.doctor1.id,
                "start_time": self._make_datetime(sunday, time(10, 0)).isoformat(),
                "end_time": self._make_datetime(sunday, time(10, 30)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # API returns either 'reason' (scheduling service) or 'detail' (serializer validation)
        self.assertTrue(
            "reason" in response.data or "detail" in response.data,
            f"Expected 'reason' or 'detail' in response, got: {response.data.keys()}"
        )


class OperationViewIntegrationTestCase(SchedulingTestMixin, TestCase):
    """Integration tests for OperationListCreateView with scheduling service."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.url = "/api/operations/"

    def test_create_operation_success(self):
        """201 response for successful operation creation."""
        monday = self._get_next_weekday(self.today, 0)

        response = self.client.post(
            self.url,
            {
                "patient_id": DUMMY_PATIENT_ID,
                "primary_surgeon": self.doctor1.id,
                "op_room": self.room1.id,
                "op_type": self.op_type.id,
                "start_time": self._make_datetime(monday, time(10, 0)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

    def test_create_operation_room_conflict_400(self):
        """400 response when room conflict is detected."""
        monday = self._get_next_weekday(self.today, 0)

        # Create existing operation
        Operation.objects.using("default").create(
            patient_id=DUMMY_PATIENT_ID + 1,
            primary_surgeon=self.doctor2,
            op_room=self.room1,
            op_type=self.op_type,
            start_time=self._make_datetime(monday, time(10, 0)),
            end_time=self._make_datetime(monday, time(11, 30)),
            status="planned",
        )

        response = self.client.post(
            self.url,
            {
                "patient_id": DUMMY_PATIENT_ID,
                "primary_surgeon": self.doctor1.id,
                "op_room": self.room1.id,
                "op_type": self.op_type.id,
                "start_time": self._make_datetime(monday, time(11, 0)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # API returns either 'conflicts' (scheduling service) or 'detail'/'reason' (serializer validation)
        self.assertTrue(
            "conflicts" in response.data or "detail" in response.data or "reason" in response.data,
            f"Expected 'conflicts', 'detail', or 'reason' in response, got: {response.data.keys()}"
        )
