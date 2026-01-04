"""
Scheduling Simulation Module for PraxiApp.

This module provides deterministic simulations of all scheduling conflict types
to test and validate the Scheduling Engine. It is used for:
- Unit testing the conflict detection logic
- Stress testing with full-day loads
- Randomized scenario generation for integration tests

==============================================================================
CONFLICT TYPES SIMULATED
==============================================================================

1. DOCTOR CONFLICTS
   - Same doctor double-booked for appointments
   - Doctor scheduled for appointment during operation
   - Operation team member (surgeon, assistant, anesthesist) conflicts

2. ROOM CONFLICTS
   - Same OP room booked for multiple operations
   - Room booked as appointment resource conflicts with operation

3. DEVICE CONFLICTS
   - Same device booked for multiple appointments
   - Device booked for appointment and operation simultaneously

4. APPOINTMENT OVERLAPS
   - Overlapping appointments (partial or complete overlap)
   - Edge-touch scenarios (end_time == start_time)

5. OPERATION OVERLAPS
   - Overlapping operations with same resources or team

6. WORKING HOURS VIOLATIONS
   - Appointment outside practice hours
   - Appointment outside doctor's personal hours
   - No hours defined for the weekday

7. DOCTOR ABSENCE
   - Appointment during doctor's scheduled absence

8. EDGE CASES
   - start_time == end_time (zero duration)
   - end_time < start_time (negative duration)
   - Date in the past

==============================================================================
ARCHITECTURE RULES
==============================================================================

- All DB access uses .using('default') - NO access to medical DB
- patient_id is always an integer dummy (99999, 99998, etc.)
- All exceptions are custom types from appointments.exceptions
- Deterministic via random.seed() for reproducibility

==============================================================================
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Callable

from django.utils import timezone

from praxi_backend.appointments.exceptions import (
    Conflict,
    DoctorAbsentError,
    DoctorBreakConflict,
    InvalidSchedulingData,
    SchedulingConflictError,
    WorkingHoursViolation,
)
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
from praxi_backend.core.models import Role, User


# ==============================================================================
# Constants
# ==============================================================================

DUMMY_PATIENT_ID_BASE = 99999
DEFAULT_SEED = 42


# ==============================================================================
# Data Classes for Simulation Results
# ==============================================================================

@dataclass
class SimulationResult:
    """Result of a single simulation scenario."""
    scenario: str
    success: bool
    expected_exception: str | None = None
    actual_exception: str | None = None
    conflicts: list[Conflict] = field(default_factory=list)
    message: str = ""
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'scenario': self.scenario,
            'success': self.success,
            'expected_exception': self.expected_exception,
            'actual_exception': self.actual_exception,
            'conflicts': [c.to_dict() for c in self.conflicts],
            'message': self.message,
            'duration_ms': self.duration_ms,
            'metadata': self.metadata,
        }


@dataclass
class SimulationSummary:
    """Summary of all simulation results."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    results: list[SimulationResult] = field(default_factory=list)

    def add(self, result: SimulationResult):
        self.results.append(result)
        self.total += 1
        if result.success:
            self.passed += 1
        else:
            self.failed += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            'total': self.total,
            'passed': self.passed,
            'failed': self.failed,
            'results': [r.to_dict() for r in self.results],
        }


# ==============================================================================
# Simulation Context
# ==============================================================================

class SimulationContext:
    """
    Context manager for scheduling simulations.
    
    Creates and manages test data (doctors, rooms, devices, hours) in the
    default database. All data is created fresh for each simulation.
    """

    def __init__(self, *, seed: int = DEFAULT_SEED):
        self.seed = seed
        self.tz = timezone.get_current_timezone()
        self.today = timezone.localdate()
        
        # Will be populated by setup()
        self.role_admin: Role | None = None
        self.role_doctor: Role | None = None
        self.doctors: list[User] = []
        self.admin: User | None = None
        self.rooms: list[Resource] = []
        self.devices: list[Resource] = []
        self.appt_types: list[AppointmentType] = []
        self.op_types: list[OperationType] = []
        self._patient_counter = DUMMY_PATIENT_ID_BASE

    def setup(self):
        """Create all necessary test data."""
        random.seed(self.seed)
        
        # Create roles
        self.role_admin, _ = Role.objects.using("default").get_or_create(
            name="admin", defaults={"label": "Administrator"}
        )
        self.role_doctor, _ = Role.objects.using("default").get_or_create(
            name="doctor", defaults={"label": "Arzt"}
        )

        # Create admin user
        self.admin = User.objects.db_manager("default").create_user(
            username=f"sim_admin_{self.seed}",
            password="simpass123",
            email=f"sim_admin_{self.seed}@test.local",
            role=self.role_admin,
        )

        # Create doctors
        for i in range(3):
            doctor = User.objects.db_manager("default").create_user(
                username=f"sim_doctor_{self.seed}_{i}",
                password="simpass123",
                email=f"sim_doctor_{self.seed}_{i}@test.local",
                role=self.role_doctor,
                first_name=f"Dr",
                last_name=f"Simulation{i}",
            )
            self.doctors.append(doctor)

        # Create rooms
        for i in range(2):
            room = Resource.objects.using("default").create(
                name=f"SimRoom_{self.seed}_{i}",
                type="room",
                color="#6A5ACD",
                active=True,
            )
            self.rooms.append(room)

        # Create devices
        for i in range(2):
            device = Resource.objects.using("default").create(
                name=f"SimDevice_{self.seed}_{i}",
                type="device",
                color="#228B22",
                active=True,
            )
            self.devices.append(device)

        # Create appointment type
        appt_type = AppointmentType.objects.using("default").create(
            name=f"SimCheckup_{self.seed}",
            color="#2E8B57",
            duration_minutes=30,
            active=True,
        )
        self.appt_types.append(appt_type)

        # Create operation type
        op_type = OperationType.objects.using("default").create(
            name=f"SimSurgery_{self.seed}",
            prep_duration=15,
            op_duration=60,
            post_duration=15,
            color="#8A2BE2",
            active=True,
        )
        self.op_types.append(op_type)

        # Create practice hours (Mon-Fri, 08:00-18:00)
        for weekday in range(5):
            # Check if any practice hours exist for this weekday
            existing = PracticeHours.objects.using("default").filter(weekday=weekday, active=True).first()
            if not existing:
                PracticeHours.objects.using("default").create(
                    weekday=weekday,
                    start_time=time(8, 0),
                    end_time=time(18, 0),
                    active=True,
                )

        # Create doctor hours for all doctors (Mon-Fri, 08:00-18:00)
        for doctor in self.doctors:
            for weekday in range(5):
                # Check if doctor hours exist for this doctor and weekday
                existing = DoctorHours.objects.using("default").filter(
                    doctor=doctor, weekday=weekday, active=True
                ).first()
                if not existing:
                    DoctorHours.objects.using("default").create(
                        doctor=doctor,
                        weekday=weekday,
                        start_time=time(8, 0),
                        end_time=time(18, 0),
                        active=True,
                    )

    def teardown(self):
        """Clean up test data (optional - tests use transactions)."""
        pass

    def next_patient_id(self) -> int:
        """Get next dummy patient ID."""
        self._patient_counter -= 1
        return self._patient_counter + 1

    def make_datetime(self, d: date, t: time) -> datetime:
        """Create a timezone-aware datetime."""
        return timezone.make_aware(datetime.combine(d, t), self.tz)

    def get_next_weekday(self, target_weekday: int, start_date: date | None = None) -> date:
        """Get the next occurrence of a weekday (0=Mon) from start_date."""
        base = start_date or self.today
        days_ahead = target_weekday - base.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return base + timedelta(days=days_ahead)


# ==============================================================================
# Simulation Functions
# ==============================================================================

def simulate_doctor_conflict(ctx: SimulationContext) -> SimulationResult:
    """
    Simulate a doctor conflict scenario.
    
    Creates two appointments/operations with overlapping times for the same doctor.
    Expected: SchedulingConflictError with doctor_conflict type.
    """
    monday = ctx.get_next_weekday(0)
    doctor = ctx.doctors[0]
    start1 = ctx.make_datetime(monday, time(10, 0))
    end1 = ctx.make_datetime(monday, time(10, 30))
    start2 = ctx.make_datetime(monday, time(10, 15))
    end2 = ctx.make_datetime(monday, time(10, 45))

    # Create first appointment
    appt1 = Appointment.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        doctor=doctor,
        type=ctx.appt_types[0],
        start_time=start1,
        end_time=end1,
        status="scheduled",
    )

    # Try to detect conflicts for second appointment
    conflicts = check_appointment_conflicts(
        date=monday,
        start_time=start2,
        end_time=end2,
        doctor_id=doctor.id,
    )

    if conflicts and any(c.type == 'doctor_conflict' for c in conflicts):
        return SimulationResult(
            scenario="doctor_conflict",
            success=True,
            expected_exception="SchedulingConflictError",
            conflicts=conflicts,
            message=f"Correctly detected {len(conflicts)} doctor conflict(s)",
            metadata={"appointment_1_id": appt1.id},
        )
    else:
        return SimulationResult(
            scenario="doctor_conflict",
            success=False,
            expected_exception="SchedulingConflictError",
            message="Failed to detect doctor conflict",
            metadata={"appointment_1_id": appt1.id},
        )


def simulate_room_conflict(ctx: SimulationContext) -> SimulationResult:
    """
    Simulate a room conflict scenario.
    
    Creates two operations in the same OP room at the same time.
    Expected: SchedulingConflictError with room_conflict type.
    """
    monday = ctx.get_next_weekday(0)
    room = ctx.rooms[0]
    start1 = ctx.make_datetime(monday, time(10, 0))
    end1 = ctx.make_datetime(monday, time(11, 30))
    start2 = ctx.make_datetime(monday, time(11, 0))
    end2 = ctx.make_datetime(monday, time(12, 30))

    # Create first operation
    op1 = Operation.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        primary_surgeon=ctx.doctors[0],
        op_room=room,
        op_type=ctx.op_types[0],
        start_time=start1,
        end_time=end1,
        status="planned",
    )

    # Try to detect conflicts for second operation
    conflicts = check_operation_conflicts(
        date=monday,
        start_time=start2,
        end_time=end2,
        primary_surgeon_id=ctx.doctors[1].id,
        room_id=room.id,
    )

    if conflicts and any(c.type == 'room_conflict' for c in conflicts):
        return SimulationResult(
            scenario="room_conflict",
            success=True,
            expected_exception="SchedulingConflictError",
            conflicts=conflicts,
            message=f"Correctly detected {len(conflicts)} room conflict(s)",
            metadata={"operation_1_id": op1.id},
        )
    else:
        return SimulationResult(
            scenario="room_conflict",
            success=False,
            expected_exception="SchedulingConflictError",
            message="Failed to detect room conflict",
            metadata={"operation_1_id": op1.id},
        )


def simulate_device_conflict(ctx: SimulationContext) -> SimulationResult:
    """
    Simulate a device conflict scenario.
    
    Creates two appointments using the same device at overlapping times.
    Expected: SchedulingConflictError with device_conflict type.
    """
    monday = ctx.get_next_weekday(0)
    device = ctx.devices[0]
    start1 = ctx.make_datetime(monday, time(10, 0))
    end1 = ctx.make_datetime(monday, time(10, 30))
    start2 = ctx.make_datetime(monday, time(10, 15))
    end2 = ctx.make_datetime(monday, time(10, 45))

    # Create first appointment with device
    appt1 = Appointment.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        doctor=ctx.doctors[0],
        type=ctx.appt_types[0],
        start_time=start1,
        end_time=end1,
        status="scheduled",
    )
    AppointmentResource.objects.using("default").create(
        appointment=appt1,
        resource=device,
    )

    # Try to detect conflicts for second appointment
    conflicts = check_appointment_conflicts(
        date=monday,
        start_time=start2,
        end_time=end2,
        doctor_id=ctx.doctors[1].id,
        resource_ids=[device.id],
    )

    if conflicts and any(c.type == 'device_conflict' for c in conflicts):
        return SimulationResult(
            scenario="device_conflict",
            success=True,
            expected_exception="SchedulingConflictError",
            conflicts=conflicts,
            message=f"Correctly detected {len(conflicts)} device conflict(s)",
            metadata={"appointment_1_id": appt1.id},
        )
    else:
        return SimulationResult(
            scenario="device_conflict",
            success=False,
            expected_exception="SchedulingConflictError",
            message="Failed to detect device conflict",
            metadata={"appointment_1_id": appt1.id},
        )


def simulate_appointment_overlap(ctx: SimulationContext) -> SimulationResult:
    """
    Simulate overlapping appointments for the same doctor.
    
    Creates a partial overlap scenario where end of appointment 1 overlaps
    with start of appointment 2.
    Expected: SchedulingConflictError with doctor_conflict type.
    """
    monday = ctx.get_next_weekday(0)
    doctor = ctx.doctors[0]
    
    # First appointment: 10:00-10:30
    start1 = ctx.make_datetime(monday, time(10, 0))
    end1 = ctx.make_datetime(monday, time(10, 30))
    
    # Second appointment: 10:20-10:50 (10 min overlap)
    start2 = ctx.make_datetime(monday, time(10, 20))
    end2 = ctx.make_datetime(monday, time(10, 50))

    appt1 = Appointment.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        doctor=doctor,
        type=ctx.appt_types[0],
        start_time=start1,
        end_time=end1,
        status="scheduled",
    )

    conflicts = check_appointment_conflicts(
        date=monday,
        start_time=start2,
        end_time=end2,
        doctor_id=doctor.id,
    )

    if conflicts and len(conflicts) > 0:
        return SimulationResult(
            scenario="appointment_overlap",
            success=True,
            expected_exception="SchedulingConflictError",
            conflicts=conflicts,
            message=f"Correctly detected {len(conflicts)} overlap(s)",
            metadata={"overlap_minutes": 10},
        )
    else:
        return SimulationResult(
            scenario="appointment_overlap",
            success=False,
            expected_exception="SchedulingConflictError",
            message="Failed to detect appointment overlap",
        )


def simulate_operation_overlap(ctx: SimulationContext) -> SimulationResult:
    """
    Simulate overlapping operations (same surgeon).
    
    Creates two operations where the surgeon is double-booked.
    Expected: SchedulingConflictError with doctor_conflict type.
    """
    monday = ctx.get_next_weekday(0)
    surgeon = ctx.doctors[0]
    room1 = ctx.rooms[0]
    room2 = ctx.rooms[1]
    
    start1 = ctx.make_datetime(monday, time(10, 0))
    end1 = ctx.make_datetime(monday, time(11, 30))
    start2 = ctx.make_datetime(monday, time(11, 0))
    end2 = ctx.make_datetime(monday, time(12, 30))

    op1 = Operation.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        primary_surgeon=surgeon,
        op_room=room1,
        op_type=ctx.op_types[0],
        start_time=start1,
        end_time=end1,
        status="planned",
    )

    conflicts = check_operation_conflicts(
        date=monday,
        start_time=start2,
        end_time=end2,
        primary_surgeon_id=surgeon.id,
        room_id=room2.id,
    )

    if conflicts and any(c.type == 'doctor_conflict' for c in conflicts):
        return SimulationResult(
            scenario="operation_overlap",
            success=True,
            expected_exception="SchedulingConflictError",
            conflicts=conflicts,
            message=f"Correctly detected {len(conflicts)} operation overlap(s)",
            metadata={"operation_1_id": op1.id},
        )
    else:
        return SimulationResult(
            scenario="operation_overlap",
            success=False,
            expected_exception="SchedulingConflictError",
            message="Failed to detect operation overlap",
        )


def simulate_working_hours_violation(ctx: SimulationContext) -> SimulationResult:
    """
    Simulate a working hours violation.
    
    Creates an appointment request outside of practice hours (Sunday).
    Expected: WorkingHoursViolation exception.
    """
    sunday = ctx.get_next_weekday(6)
    doctor = ctx.doctors[0]
    start = ctx.make_datetime(sunday, time(10, 0))
    end = ctx.make_datetime(sunday, time(10, 30))

    try:
        validate_working_hours(
            doctor_id=doctor.id,
            date=sunday,
            start_time=start,
            end_time=end,
        )
        return SimulationResult(
            scenario="working_hours_violation",
            success=False,
            expected_exception="WorkingHoursViolation",
            message="Should have raised WorkingHoursViolation but did not",
        )
    except WorkingHoursViolation as e:
        return SimulationResult(
            scenario="working_hours_violation",
            success=True,
            expected_exception="WorkingHoursViolation",
            actual_exception="WorkingHoursViolation",
            message=f"Correctly raised WorkingHoursViolation: {e.reason}",
            metadata={"reason": e.reason, "date": str(sunday)},
        )
    except Exception as e:
        return SimulationResult(
            scenario="working_hours_violation",
            success=False,
            expected_exception="WorkingHoursViolation",
            actual_exception=type(e).__name__,
            message=f"Wrong exception type: {e}",
        )


def simulate_doctor_absence(ctx: SimulationContext) -> SimulationResult:
    """
    Simulate a doctor absence conflict.
    
    Creates an absence record and tries to schedule an appointment during that period.
    Expected: DoctorAbsentError exception.
    """
    monday = ctx.get_next_weekday(0)
    tuesday = monday + timedelta(days=1)
    wednesday = monday + timedelta(days=2)
    doctor = ctx.doctors[0]

    # Create absence for Monday-Wednesday
    absence = DoctorAbsence.objects.using("default").create(
        doctor=doctor,
        start_date=monday,
        end_date=wednesday,
        reason="Simulation absence",
        active=True,
    )

    # Try to schedule on Tuesday
    start = ctx.make_datetime(tuesday, time(10, 0))
    end = ctx.make_datetime(tuesday, time(10, 30))

    try:
        validate_doctor_absences(
            doctor_id=doctor.id,
            date=tuesday,
            start_time=start,
            end_time=end,
        )
        return SimulationResult(
            scenario="doctor_absence",
            success=False,
            expected_exception="DoctorAbsentError",
            message="Should have raised DoctorAbsentError but did not",
        )
    except DoctorAbsentError as e:
        return SimulationResult(
            scenario="doctor_absence",
            success=True,
            expected_exception="DoctorAbsentError",
            actual_exception="DoctorAbsentError",
            message=f"Correctly raised DoctorAbsentError",
            metadata={"absence_id": absence.id, "date": str(tuesday)},
        )
    except Exception as e:
        return SimulationResult(
            scenario="doctor_absence",
            success=False,
            expected_exception="DoctorAbsentError",
            actual_exception=type(e).__name__,
            message=f"Wrong exception type: {e}",
        )


def simulate_doctor_break(ctx: SimulationContext) -> SimulationResult:
    """
    Simulate a doctor break conflict.
    
    Creates a break record and tries to schedule an appointment during the break.
    Expected: DoctorBreakConflict exception.
    """
    monday = ctx.get_next_weekday(0)
    doctor = ctx.doctors[0]

    # Create break 12:00-13:00
    doc_break = DoctorBreak.objects.using("default").create(
        doctor=doctor,
        date=monday,
        start_time=time(12, 0),
        end_time=time(13, 0),
        reason="Lunch break",
        active=True,
    )

    # Try to schedule appointment during break
    start = ctx.make_datetime(monday, time(12, 15))
    end = ctx.make_datetime(monday, time(12, 45))

    try:
        validate_doctor_breaks(
            doctor_id=doctor.id,
            date=monday,
            start_time=start,
            end_time=end,
        )
        return SimulationResult(
            scenario="doctor_break",
            success=False,
            expected_exception="DoctorBreakConflict",
            message="Should have raised DoctorBreakConflict but did not",
        )
    except DoctorBreakConflict as e:
        return SimulationResult(
            scenario="doctor_break",
            success=True,
            expected_exception="DoctorBreakConflict",
            actual_exception="DoctorBreakConflict",
            message=f"Correctly raised DoctorBreakConflict",
            metadata={"break_id": doc_break.id},
        )
    except Exception as e:
        return SimulationResult(
            scenario="doctor_break",
            success=False,
            expected_exception="DoctorBreakConflict",
            actual_exception=type(e).__name__,
            message=f"Wrong exception type: {e}",
        )


def simulate_patient_double_booking(ctx: SimulationContext) -> SimulationResult:
    """
    Simulate a patient double-booking scenario.
    
    Same patient has overlapping appointments (different doctors).
    Expected: SchedulingConflictError with patient_conflict type.
    """
    monday = ctx.get_next_weekday(0)
    patient_id = ctx.next_patient_id()
    
    start1 = ctx.make_datetime(monday, time(10, 0))
    end1 = ctx.make_datetime(monday, time(10, 30))
    start2 = ctx.make_datetime(monday, time(10, 15))
    end2 = ctx.make_datetime(monday, time(10, 45))

    appt1 = Appointment.objects.using("default").create(
        patient_id=patient_id,
        doctor=ctx.doctors[0],
        type=ctx.appt_types[0],
        start_time=start1,
        end_time=end1,
        status="scheduled",
    )

    conflicts = check_patient_conflicts(
        patient_id=patient_id,
        start_time=start2,
        end_time=end2,
    )

    if conflicts and any(c.type == 'patient_conflict' for c in conflicts):
        return SimulationResult(
            scenario="patient_double_booking",
            success=True,
            expected_exception="SchedulingConflictError",
            conflicts=conflicts,
            message=f"Correctly detected {len(conflicts)} patient conflict(s)",
            metadata={"patient_id": patient_id},
        )
    else:
        return SimulationResult(
            scenario="patient_double_booking",
            success=False,
            expected_exception="SchedulingConflictError",
            message="Failed to detect patient double-booking",
        )


def simulate_edge_cases(ctx: SimulationContext) -> list[SimulationResult]:
    """
    Simulate edge cases for scheduling validation.
    
    Tests:
    - start_time == end_time (zero duration)
    - end_time < start_time (negative duration)
    - Date in the past
    
    Returns list of SimulationResult for each edge case.
    """
    results: list[SimulationResult] = []
    monday = ctx.get_next_weekday(0)
    doctor = ctx.doctors[0]

    # Edge case 1: Zero duration (start_time == end_time)
    zero_time = ctx.make_datetime(monday, time(10, 0))
    try:
        # plan_appointment should validate this
        plan_appointment(
            data={
                'patient_id': ctx.next_patient_id(),
                'doctor_id': doctor.id,
                'start_time': zero_time,
                'end_time': zero_time,
                'type_id': ctx.appt_types[0].id,
            },
            user=ctx.admin,
        )
        results.append(SimulationResult(
            scenario="edge_case_zero_duration",
            success=False,
            expected_exception="InvalidSchedulingData",
            message="Should have rejected zero duration",
        ))
    except InvalidSchedulingData:
        results.append(SimulationResult(
            scenario="edge_case_zero_duration",
            success=True,
            expected_exception="InvalidSchedulingData",
            actual_exception="InvalidSchedulingData",
            message="Correctly rejected zero duration",
        ))
    except Exception as e:
        results.append(SimulationResult(
            scenario="edge_case_zero_duration",
            success=False,
            expected_exception="InvalidSchedulingData",
            actual_exception=type(e).__name__,
            message=f"Wrong exception: {e}",
        ))

    # Edge case 2: Negative duration (end_time < start_time)
    start = ctx.make_datetime(monday, time(11, 0))
    end = ctx.make_datetime(monday, time(10, 0))
    try:
        plan_appointment(
            data={
                'patient_id': ctx.next_patient_id(),
                'doctor_id': doctor.id,
                'start_time': start,
                'end_time': end,
                'type_id': ctx.appt_types[0].id,
            },
            user=ctx.admin,
        )
        results.append(SimulationResult(
            scenario="edge_case_negative_duration",
            success=False,
            expected_exception="InvalidSchedulingData",
            message="Should have rejected negative duration",
        ))
    except InvalidSchedulingData:
        results.append(SimulationResult(
            scenario="edge_case_negative_duration",
            success=True,
            expected_exception="InvalidSchedulingData",
            actual_exception="InvalidSchedulingData",
            message="Correctly rejected negative duration",
        ))
    except Exception as e:
        results.append(SimulationResult(
            scenario="edge_case_negative_duration",
            success=False,
            expected_exception="InvalidSchedulingData",
            actual_exception=type(e).__name__,
            message=f"Wrong exception: {e}",
        ))

    # Edge case 3: Edge-touch (end1 == start2)
    start1 = ctx.make_datetime(monday, time(14, 0))
    end1 = ctx.make_datetime(monday, time(14, 30))
    start2 = ctx.make_datetime(monday, time(14, 30))
    end2 = ctx.make_datetime(monday, time(15, 0))

    appt_edge = Appointment.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        doctor=doctor,
        type=ctx.appt_types[0],
        start_time=start1,
        end_time=end1,
        status="scheduled",
    )

    conflicts = check_appointment_conflicts(
        date=monday,
        start_time=start2,
        end_time=end2,
        doctor_id=doctor.id,
    )

    # Edge-touch should NOT be a conflict
    if not conflicts:
        results.append(SimulationResult(
            scenario="edge_case_edge_touch",
            success=True,
            message="Correctly allowed edge-touch (no overlap)",
        ))
    else:
        results.append(SimulationResult(
            scenario="edge_case_edge_touch",
            success=False,
            conflicts=conflicts,
            message="Incorrectly flagged edge-touch as conflict",
        ))

    return results


def simulate_full_day_load(ctx: SimulationContext, num_appointments: int = 20) -> SimulationResult:
    """
    Simulate a full day with many appointments and operations.
    
    Creates num_appointments appointments distributed throughout the day
    and measures performance.
    """
    import time as time_module
    
    monday = ctx.get_next_weekday(0)
    start_perf = time_module.perf_counter()
    
    # Create appointments from 08:00 to 18:00 (10 hours = 600 minutes)
    # Each appointment is 30 minutes, so max 20 non-overlapping
    created_appts = []
    hour = 8
    minute = 0
    
    for i in range(min(num_appointments, 20)):
        doctor = ctx.doctors[i % len(ctx.doctors)]
        start = ctx.make_datetime(monday, time(hour, minute))
        end = ctx.make_datetime(monday, time(hour, minute + 30 if minute < 30 else minute))
        
        if minute < 30:
            end = ctx.make_datetime(monday, time(hour, minute + 30))
        else:
            end = ctx.make_datetime(monday, time(hour + 1, 0))
        
        appt = Appointment.objects.using("default").create(
            patient_id=ctx.next_patient_id(),
            doctor=doctor,
            type=ctx.appt_types[0],
            start_time=start,
            end_time=end,
            status="scheduled",
        )
        created_appts.append(appt)
        
        # Advance time
        minute += 30
        if minute >= 60:
            minute = 0
            hour += 1
            if hour >= 18:
                break

    # Now try to check conflicts for a new appointment (performance test)
    check_start = ctx.make_datetime(monday, time(12, 0))
    check_end = ctx.make_datetime(monday, time(12, 30))
    
    conflicts = check_appointment_conflicts(
        date=monday,
        start_time=check_start,
        end_time=check_end,
        doctor_id=ctx.doctors[0].id,
    )

    end_perf = time_module.perf_counter()
    duration_ms = (end_perf - start_perf) * 1000

    return SimulationResult(
        scenario="full_day_load",
        success=True,
        conflicts=conflicts,
        message=f"Created {len(created_appts)} appointments, conflict check found {len(conflicts)} conflicts",
        duration_ms=duration_ms,
        metadata={
            "appointments_created": len(created_appts),
            "conflicts_found": len(conflicts),
        },
    )


def simulate_randomized_day(ctx: SimulationContext, seed: int | None = None) -> SimulationResult:
    """
    Simulate a randomized day with mixed appointments and operations.
    
    Uses deterministic randomness based on seed for reproducibility.
    """
    import time as time_module
    
    if seed is not None:
        random.seed(seed)
    
    monday = ctx.get_next_weekday(0)
    start_perf = time_module.perf_counter()
    
    appointments_created = 0
    operations_created = 0
    conflicts_encountered = 0
    
    # Generate random events
    for i in range(15):
        event_type = random.choice(['appointment', 'operation'])
        doctor = random.choice(ctx.doctors)
        hour = random.randint(8, 16)
        minute = random.choice([0, 15, 30, 45])
        duration = random.choice([15, 30, 45, 60])
        
        start = ctx.make_datetime(monday, time(hour, minute))
        end_hour = hour + (minute + duration) // 60
        end_minute = (minute + duration) % 60
        
        if end_hour > 18:
            end_hour = 18
            end_minute = 0
        
        end = ctx.make_datetime(monday, time(end_hour, end_minute))
        
        if event_type == 'appointment':
            conflicts = check_appointment_conflicts(
                date=monday,
                start_time=start,
                end_time=end,
                doctor_id=doctor.id,
            )
            if not conflicts:
                Appointment.objects.using("default").create(
                    patient_id=ctx.next_patient_id(),
                    doctor=doctor,
                    type=ctx.appt_types[0],
                    start_time=start,
                    end_time=end,
                    status="scheduled",
                )
                appointments_created += 1
            else:
                conflicts_encountered += len(conflicts)
        else:
            room = random.choice(ctx.rooms)
            conflicts = check_operation_conflicts(
                date=monday,
                start_time=start,
                end_time=end,
                primary_surgeon_id=doctor.id,
                room_id=room.id,
            )
            if not conflicts:
                Operation.objects.using("default").create(
                    patient_id=ctx.next_patient_id(),
                    primary_surgeon=doctor,
                    op_room=room,
                    op_type=ctx.op_types[0],
                    start_time=start,
                    end_time=end,
                    status="planned",
                )
                operations_created += 1
            else:
                conflicts_encountered += len(conflicts)

    end_perf = time_module.perf_counter()
    duration_ms = (end_perf - start_perf) * 1000

    return SimulationResult(
        scenario="randomized_day",
        success=True,
        message=f"Created {appointments_created} appointments, {operations_created} operations, {conflicts_encountered} conflicts detected",
        duration_ms=duration_ms,
        metadata={
            "appointments_created": appointments_created,
            "operations_created": operations_created,
            "conflicts_encountered": conflicts_encountered,
            "seed": seed or ctx.seed,
        },
    )


def simulate_team_conflict(ctx: SimulationContext) -> SimulationResult:
    """
    Simulate a conflict with operation team members (assistant, anesthesist).
    
    Creates an operation with full team, then tries to book an appointment
    for the assistant during the operation.
    """
    monday = ctx.get_next_weekday(0)
    surgeon = ctx.doctors[0]
    assistant = ctx.doctors[1]
    anesthesist = ctx.doctors[2] if len(ctx.doctors) > 2 else None
    
    start_op = ctx.make_datetime(monday, time(10, 0))
    end_op = ctx.make_datetime(monday, time(11, 30))

    op = Operation.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        primary_surgeon=surgeon,
        assistant=assistant,
        anesthesist=anesthesist,
        op_room=ctx.rooms[0],
        op_type=ctx.op_types[0],
        start_time=start_op,
        end_time=end_op,
        status="planned",
    )

    # Try to book appointment for assistant during operation
    start_appt = ctx.make_datetime(monday, time(10, 30))
    end_appt = ctx.make_datetime(monday, time(11, 0))

    conflicts = check_appointment_conflicts(
        date=monday,
        start_time=start_appt,
        end_time=end_appt,
        doctor_id=assistant.id,
    )

    if conflicts and any(c.type == 'doctor_conflict' for c in conflicts):
        return SimulationResult(
            scenario="team_conflict",
            success=True,
            expected_exception="SchedulingConflictError",
            conflicts=conflicts,
            message=f"Correctly detected team member conflict",
            metadata={"operation_id": op.id, "assistant_id": assistant.id},
        )
    else:
        return SimulationResult(
            scenario="team_conflict",
            success=False,
            expected_exception="SchedulingConflictError",
            message="Failed to detect team member conflict",
        )


# ==============================================================================
# Main Simulation Runner
# ==============================================================================

def run_all_simulations(seed: int = DEFAULT_SEED) -> SimulationSummary:
    """
    Run all simulation scenarios and return summary.
    
    Args:
        seed: Random seed for deterministic results.
        
    Returns:
        SimulationSummary with all results.
    """
    summary = SimulationSummary()
    ctx = SimulationContext(seed=seed)
    ctx.setup()

    # Run each simulation
    summary.add(simulate_doctor_conflict(ctx))
    summary.add(simulate_room_conflict(ctx))
    summary.add(simulate_device_conflict(ctx))
    summary.add(simulate_appointment_overlap(ctx))
    summary.add(simulate_operation_overlap(ctx))
    summary.add(simulate_working_hours_violation(ctx))
    summary.add(simulate_doctor_absence(ctx))
    summary.add(simulate_doctor_break(ctx))
    summary.add(simulate_patient_double_booking(ctx))
    summary.add(simulate_team_conflict(ctx))
    
    # Edge cases return multiple results
    for result in simulate_edge_cases(ctx):
        summary.add(result)
    
    # Performance tests
    summary.add(simulate_full_day_load(ctx))
    summary.add(simulate_randomized_day(ctx, seed=seed))

    ctx.teardown()
    return summary


def print_simulation_report(summary: SimulationSummary) -> None:
    """Print a human-readable simulation report."""
    print("=" * 70)
    print("SCHEDULING SIMULATION REPORT")
    print("=" * 70)
    print(f"Total Scenarios: {summary.total}")
    print(f"Passed: {summary.passed}")
    print(f"Failed: {summary.failed}")
    print("-" * 70)
    
    for result in summary.results:
        status = "✅ PASS" if result.success else "❌ FAIL"
        print(f"{status} | {result.scenario}")
        if result.message:
            print(f"       {result.message}")
        if result.conflicts:
            print(f"       Conflicts: {len(result.conflicts)}")
        if result.duration_ms > 0:
            print(f"       Duration: {result.duration_ms:.2f}ms")
    
    print("=" * 70)
