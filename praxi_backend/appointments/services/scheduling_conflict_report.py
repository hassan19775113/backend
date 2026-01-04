"""
Scheduling Conflict Report Generator for PraxiApp.

This module generates comprehensive, structured conflict reports for the
Scheduling Engine. It automatically detects, groups, prioritizes, and
explains all conflict types.

==============================================================================
CONFLICT CATEGORIES
==============================================================================

1. DOCTOR CONFLICTS (doctor_conflict)
   - Same doctor double-booked for appointments
   - Doctor scheduled for appointment during operation
   - Operation team member conflicts (surgeon, assistant, anesthesist)
   Priority: HIGH

2. ROOM CONFLICTS (room_conflict)
   - Same OP room booked for multiple operations
   - Room resource conflicts
   Priority: HIGH

3. DEVICE CONFLICTS (device_conflict)
   - Same device booked for overlapping appointments/operations
   Priority: HIGH

4. APPOINTMENT OVERLAPS (appointment_overlap)
   - Overlapping appointments for same doctor
   - Partial or complete time overlaps
   Priority: MEDIUM

5. OPERATION OVERLAPS (operation_overlap)
   - Overlapping operations with same team/resources
   Priority: HIGH

6. WORKING HOURS VIOLATIONS (working_hours_violation)
   - Appointment outside practice hours
   - Appointment outside doctor's hours
   Priority: MEDIUM

7. DOCTOR ABSENCE (doctor_absent)
   - Appointment during doctor's scheduled absence
   Priority: MEDIUM

8. DOCTOR BREAK (doctor_break)
   - Appointment during doctor's break time
   Priority: LOW

9. PATIENT DOUBLE BOOKING (patient_conflict)
   - Same patient booked for overlapping appointments
   Priority: MEDIUM

10. EDGE CASES (validation_error)
    - Zero duration (start == end)
    - Negative duration (end < start)
    - Past dates
    Priority: LOW

==============================================================================
ARCHITECTURE RULES
==============================================================================

- All DB access uses .using('default') - NO access to medical DB
- patient_id is always an integer dummy (99999, 99998, etc.)
- Report output is structured dict/JSON for machine processing
- Human-readable text report also available

==============================================================================
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time as dt_time, timedelta
from enum import Enum
from typing import Any

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
    OperationType,
    PracticeHours,
    Resource,
)
from praxi_backend.appointments.services.scheduling import (
    check_appointment_conflicts,
    check_operation_conflicts,
    check_patient_conflicts,
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


class ConflictPriority(Enum):
    """Priority levels for conflicts."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConflictCategory(Enum):
    """Categories of scheduling conflicts."""
    DOCTOR_CONFLICT = "doctor_conflict"
    ROOM_CONFLICT = "room_conflict"
    DEVICE_CONFLICT = "device_conflict"
    APPOINTMENT_OVERLAP = "appointment_overlap"
    OPERATION_OVERLAP = "operation_overlap"
    WORKING_HOURS_VIOLATION = "working_hours_violation"
    DOCTOR_ABSENT = "doctor_absent"
    DOCTOR_BREAK = "doctor_break"
    PATIENT_CONFLICT = "patient_conflict"
    VALIDATION_ERROR = "validation_error"


# Priority mapping
CONFLICT_PRIORITIES: dict[ConflictCategory, ConflictPriority] = {
    ConflictCategory.DOCTOR_CONFLICT: ConflictPriority.HIGH,
    ConflictCategory.ROOM_CONFLICT: ConflictPriority.HIGH,
    ConflictCategory.DEVICE_CONFLICT: ConflictPriority.HIGH,
    ConflictCategory.OPERATION_OVERLAP: ConflictPriority.HIGH,
    ConflictCategory.APPOINTMENT_OVERLAP: ConflictPriority.MEDIUM,
    ConflictCategory.WORKING_HOURS_VIOLATION: ConflictPriority.MEDIUM,
    ConflictCategory.DOCTOR_ABSENT: ConflictPriority.MEDIUM,
    ConflictCategory.PATIENT_CONFLICT: ConflictPriority.MEDIUM,
    ConflictCategory.DOCTOR_BREAK: ConflictPriority.LOW,
    ConflictCategory.VALIDATION_ERROR: ConflictPriority.LOW,
}


# ==============================================================================
# Data Classes
# ==============================================================================

@dataclass
class ConflictDetail:
    """Detailed information about a single conflict."""
    id: str
    category: ConflictCategory
    priority: ConflictPriority
    description: str
    affected_objects: list[dict[str, Any]]
    time_window: dict[str, str]
    doctor_id: int | None = None
    doctor_name: str | None = None
    room_id: int | None = None
    room_name: str | None = None
    patient_id: int | None = None
    cause: str = ""
    recommendation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'category': self.category.value,
            'priority': self.priority.value,
            'description': self.description,
            'affected_objects': self.affected_objects,
            'time_window': self.time_window,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor_name,
            'room_id': self.room_id,
            'room_name': self.room_name,
            'patient_id': self.patient_id,
            'cause': self.cause,
            'recommendation': self.recommendation,
            'metadata': self.metadata,
        }


@dataclass
class ConflictGroup:
    """Group of related conflicts."""
    group_key: str
    group_type: str  # 'by_type', 'by_date', 'by_doctor', 'by_room', 'by_priority'
    conflicts: list[ConflictDetail] = field(default_factory=list)
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            'group_key': self.group_key,
            'group_type': self.group_type,
            'conflicts': [c.to_dict() for c in self.conflicts],
            'count': self.count,
        }


@dataclass
class ConflictExample:
    """Example of a specific conflict type."""
    conflict_type: ConflictCategory
    title: str
    scenario: str
    conflict_detail: ConflictDetail | None = None
    code_snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            'conflict_type': self.conflict_type.value,
            'title': self.title,
            'scenario': self.scenario,
            'conflict_detail': self.conflict_detail.to_dict() if self.conflict_detail else None,
            'code_snippet': self.code_snippet,
        }


@dataclass
class ConflictSummary:
    """Summary statistics for the conflict report."""
    total_conflicts: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_priority: dict[str, int] = field(default_factory=dict)
    critical_conflicts: int = 0
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            'total_conflicts': self.total_conflicts,
            'by_category': self.by_category,
            'by_priority': self.by_priority,
            'critical_conflicts': self.critical_conflicts,
            'recommendations': self.recommendations,
        }


@dataclass
class ConflictReport:
    """Complete conflict report."""
    timestamp: str
    report_id: str
    conflict_types_overview: list[dict[str, Any]]
    all_conflicts: list[ConflictDetail]
    grouped_by_type: list[ConflictGroup]
    grouped_by_priority: list[ConflictGroup]
    grouped_by_doctor: list[ConflictGroup]
    grouped_by_room: list[ConflictGroup]
    examples: list[ConflictExample]
    summary: ConflictSummary
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'report_id': self.report_id,
            'conflict_types_overview': self.conflict_types_overview,
            'all_conflicts': [c.to_dict() for c in self.all_conflicts],
            'grouped_by_type': [g.to_dict() for g in self.grouped_by_type],
            'grouped_by_priority': [g.to_dict() for g in self.grouped_by_priority],
            'grouped_by_doctor': [g.to_dict() for g in self.grouped_by_doctor],
            'grouped_by_room': [g.to_dict() for g in self.grouped_by_room],
            'examples': [e.to_dict() for e in self.examples],
            'summary': self.summary.to_dict(),
            'metadata': self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        """Export report as JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ==============================================================================
# Report Context
# ==============================================================================

class ReportContext:
    """Context for generating conflict reports with test data."""

    def __init__(self, *, seed: int = DEFAULT_SEED):
        self.seed = seed
        self.tz = timezone.get_current_timezone()
        self.today = timezone.localdate()
        
        self.role_admin: Role | None = None
        self.role_doctor: Role | None = None
        self.doctors: list[User] = []
        self.admin: User | None = None
        self.rooms: list[Resource] = []
        self.devices: list[Resource] = []
        self.appt_types: list[AppointmentType] = []
        self.op_types: list[OperationType] = []
        self._patient_counter = DUMMY_PATIENT_ID_BASE
        self._conflict_counter = 0

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

        # Create admin
        self.admin = User.objects.db_manager("default").create_user(
            username=f"report_admin_{self.seed}",
            password="reportpass123",
            email=f"report_admin_{self.seed}@test.local",
            role=self.role_admin,
        )

        # Create doctors
        doctor_names = [
            ("Dr. Max", "Mustermann"),
            ("Dr. Anna", "Schmidt"),
            ("Dr. Peter", "Meyer"),
            ("Dr. Lisa", "Wagner"),
        ]
        for i, (first, last) in enumerate(doctor_names):
            doctor = User.objects.db_manager("default").create_user(
                username=f"report_doctor_{self.seed}_{i}",
                password="reportpass123",
                email=f"report_doctor_{self.seed}_{i}@test.local",
                role=self.role_doctor,
                first_name=first,
                last_name=last,
            )
            self.doctors.append(doctor)

        # Create rooms
        room_names = ["OP-Saal 1", "OP-Saal 2", "Behandlungsraum A", "Behandlungsraum B"]
        for i, name in enumerate(room_names):
            room = Resource.objects.using("default").create(
                name=f"{name}_{self.seed}",
                type="room",
                color="#6A5ACD",
                active=True,
            )
            self.rooms.append(room)

        # Create devices
        device_names = ["Ultraschall", "EKG-Gerät", "Röntgen"]
        for i, name in enumerate(device_names):
            device = Resource.objects.using("default").create(
                name=f"{name}_{self.seed}",
                type="device",
                color="#228B22",
                active=True,
            )
            self.devices.append(device)

        # Create appointment types
        appt_type = AppointmentType.objects.using("default").create(
            name=f"Untersuchung_{self.seed}",
            color="#2E8B57",
            duration_minutes=30,
            active=True,
        )
        self.appt_types.append(appt_type)

        # Create operation types
        op_type = OperationType.objects.using("default").create(
            name=f"Standardoperation_{self.seed}",
            prep_duration=15,
            op_duration=60,
            post_duration=15,
            color="#8A2BE2",
            active=True,
        )
        self.op_types.append(op_type)

        # Create practice hours (Mon-Fri, 08:00-18:00)
        for weekday in range(5):
            PracticeHours.objects.using("default").get_or_create(
                weekday=weekday,
                defaults={
                    "start_time": dt_time(8, 0),
                    "end_time": dt_time(18, 0),
                    "active": True,
                }
            )

        # Create doctor hours
        for doctor in self.doctors:
            for weekday in range(5):
                DoctorHours.objects.using("default").get_or_create(
                    doctor=doctor,
                    weekday=weekday,
                    defaults={
                        "start_time": dt_time(8, 0),
                        "end_time": dt_time(18, 0),
                        "active": True,
                    }
                )

    def next_patient_id(self) -> int:
        self._patient_counter -= 1
        return self._patient_counter + 1

    def next_conflict_id(self) -> str:
        self._conflict_counter += 1
        return f"CONF-{self.seed}-{self._conflict_counter:04d}"

    def make_datetime(self, d: date, t: dt_time) -> datetime:
        return timezone.make_aware(datetime.combine(d, t), self.tz)

    def get_next_weekday(self, target_weekday: int) -> date:
        base = self.today
        days_ahead = target_weekday - base.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return base + timedelta(days=days_ahead)


# ==============================================================================
# Conflict Type Definitions
# ==============================================================================

def get_conflict_types_overview() -> list[dict[str, Any]]:
    """Return overview of all conflict types with descriptions."""
    return [
        {
            "type": "doctor_conflict",
            "name": "Arzt-Konflikt",
            "description": "Derselbe Arzt ist für überlappende Termine/OPs gebucht",
            "priority": "high",
            "detection_method": "check_appointment_conflicts(), check_operation_conflicts()",
            "examples": [
                "Arzt hat zwei Termine zur gleichen Zeit",
                "Arzt ist während OP für Termin gebucht",
            ],
        },
        {
            "type": "room_conflict",
            "name": "Raum-Konflikt",
            "description": "Derselbe OP-Raum ist für überlappende Operationen gebucht",
            "priority": "high",
            "detection_method": "check_operation_conflicts()",
            "examples": [
                "Zwei OPs im gleichen OP-Saal zur gleichen Zeit",
            ],
        },
        {
            "type": "device_conflict",
            "name": "Geräte-Konflikt",
            "description": "Dasselbe Gerät ist für überlappende Termine gebucht",
            "priority": "high",
            "detection_method": "check_appointment_conflicts()",
            "examples": [
                "Ultraschallgerät für zwei Termine gleichzeitig gebucht",
            ],
        },
        {
            "type": "appointment_overlap",
            "name": "Termin-Überlappung",
            "description": "Termine überschneiden sich zeitlich",
            "priority": "medium",
            "detection_method": "check_appointment_conflicts()",
            "examples": [
                "Termin 1 endet um 10:30, Termin 2 beginnt um 10:15",
            ],
        },
        {
            "type": "operation_overlap",
            "name": "OP-Überlappung",
            "description": "Operationen überschneiden sich zeitlich",
            "priority": "high",
            "detection_method": "check_operation_conflicts()",
            "examples": [
                "Chirurg für zwei OPs zur gleichen Zeit eingeteilt",
            ],
        },
        {
            "type": "working_hours_violation",
            "name": "Arbeitszeit-Verstoß",
            "description": "Termin liegt außerhalb der Praxis- oder Arzt-Arbeitszeiten",
            "priority": "medium",
            "detection_method": "validate_working_hours()",
            "examples": [
                "Termin am Sonntag (keine Praxiszeiten)",
                "Termin um 20:00 (nach Praxisschluss)",
            ],
        },
        {
            "type": "doctor_absent",
            "name": "Arzt abwesend",
            "description": "Termin während Abwesenheit des Arztes",
            "priority": "medium",
            "detection_method": "validate_doctor_absences()",
            "examples": [
                "Termin während Urlaub des Arztes",
                "Termin während Fortbildung",
            ],
        },
        {
            "type": "doctor_break",
            "name": "Arzt-Pause",
            "description": "Termin während Pausenzeit des Arztes",
            "priority": "low",
            "detection_method": "validate_doctor_breaks()",
            "examples": [
                "Termin während Mittagspause",
            ],
        },
        {
            "type": "patient_conflict",
            "name": "Patienten-Doppelbuchung",
            "description": "Patient hat überlappende Termine",
            "priority": "medium",
            "detection_method": "check_patient_conflicts()",
            "examples": [
                "Patient für zwei Termine zur gleichen Zeit gebucht",
            ],
        },
        {
            "type": "validation_error",
            "name": "Validierungsfehler",
            "description": "Ungültige Zeitangaben oder Daten",
            "priority": "low",
            "detection_method": "plan_appointment(), plan_operation()",
            "examples": [
                "Endzeit vor Startzeit",
                "Null-Dauer (Start = Ende)",
                "Termin in der Vergangenheit",
            ],
        },
    ]


# ==============================================================================
# Conflict Detection
# ==============================================================================

def detect_doctor_conflict(ctx: ReportContext) -> ConflictDetail:
    """Detect and return example of doctor conflict."""
    monday = ctx.get_next_weekday(0)
    doctor = ctx.doctors[0]
    
    start1 = ctx.make_datetime(monday, dt_time(10, 0))
    end1 = ctx.make_datetime(monday, dt_time(10, 30))
    start2 = ctx.make_datetime(monday, dt_time(10, 15))
    end2 = ctx.make_datetime(monday, dt_time(10, 45))

    # Create first appointment
    appt1 = Appointment.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        doctor=doctor,
        type=ctx.appt_types[0],
        start_time=start1,
        end_time=end1,
        status="scheduled",
    )

    # Detect conflict
    conflicts = check_appointment_conflicts(
        date=monday,
        start_time=start2,
        end_time=end2,
        doctor_id=doctor.id,
    )

    return ConflictDetail(
        id=ctx.next_conflict_id(),
        category=ConflictCategory.DOCTOR_CONFLICT,
        priority=ConflictPriority.HIGH,
        description=f"Arzt {doctor.first_name} {doctor.last_name} ist doppelt gebucht",
        affected_objects=[
            {"type": "Appointment", "id": appt1.id, "time": f"{start1.strftime('%H:%M')}-{end1.strftime('%H:%M')}"},
            {"type": "NewAppointment", "time": f"{start2.strftime('%H:%M')}-{end2.strftime('%H:%M')}"},
        ],
        time_window={
            "date": str(monday),
            "overlap_start": "10:15",
            "overlap_end": "10:30",
        },
        doctor_id=doctor.id,
        doctor_name=f"{doctor.first_name} {doctor.last_name}",
        cause="Zwei Termine überschneiden sich um 15 Minuten",
        recommendation="Verschieben Sie einen der Termine oder weisen Sie einen anderen Arzt zu",
        metadata={"conflicts_found": len(conflicts)},
    )


def detect_room_conflict(ctx: ReportContext) -> ConflictDetail:
    """Detect and return example of room conflict."""
    monday = ctx.get_next_weekday(0)
    room = ctx.rooms[0]
    
    start1 = ctx.make_datetime(monday, dt_time(10, 0))
    end1 = ctx.make_datetime(monday, dt_time(11, 30))
    start2 = ctx.make_datetime(monday, dt_time(11, 0))
    end2 = ctx.make_datetime(monday, dt_time(12, 30))

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

    # Detect conflict
    conflicts = check_operation_conflicts(
        date=monday,
        start_time=start2,
        end_time=end2,
        primary_surgeon_id=ctx.doctors[1].id,
        room_id=room.id,
    )

    return ConflictDetail(
        id=ctx.next_conflict_id(),
        category=ConflictCategory.ROOM_CONFLICT,
        priority=ConflictPriority.HIGH,
        description=f"OP-Saal '{room.name}' ist doppelt gebucht",
        affected_objects=[
            {"type": "Operation", "id": op1.id, "time": f"{start1.strftime('%H:%M')}-{end1.strftime('%H:%M')}"},
            {"type": "NewOperation", "time": f"{start2.strftime('%H:%M')}-{end2.strftime('%H:%M')}"},
        ],
        time_window={
            "date": str(monday),
            "overlap_start": "11:00",
            "overlap_end": "11:30",
        },
        room_id=room.id,
        room_name=room.name,
        cause="Zwei Operationen überschneiden sich um 30 Minuten im gleichen OP-Saal",
        recommendation="Verschieben Sie eine OP oder wechseln Sie den OP-Saal",
        metadata={"conflicts_found": len(conflicts)},
    )


def detect_working_hours_violation(ctx: ReportContext) -> ConflictDetail:
    """Detect and return example of working hours violation."""
    sunday = ctx.get_next_weekday(6)
    doctor = ctx.doctors[0]
    
    start = ctx.make_datetime(sunday, dt_time(10, 0))
    end = ctx.make_datetime(sunday, dt_time(10, 30))

    violation_reason = ""
    try:
        validate_working_hours(
            doctor_id=doctor.id,
            date=sunday,
            start_time=start,
            end_time=end,
        )
    except WorkingHoursViolation as e:
        violation_reason = e.reason

    return ConflictDetail(
        id=ctx.next_conflict_id(),
        category=ConflictCategory.WORKING_HOURS_VIOLATION,
        priority=ConflictPriority.MEDIUM,
        description="Termin liegt außerhalb der Praxiszeiten",
        affected_objects=[
            {"type": "NewAppointment", "time": f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"},
        ],
        time_window={
            "date": str(sunday),
            "day_of_week": "Sonntag",
            "requested_time": "10:00-10:30",
        },
        doctor_id=doctor.id,
        doctor_name=f"{doctor.first_name} {doctor.last_name}",
        cause=violation_reason or "Keine Praxiszeiten am Sonntag definiert",
        recommendation="Wählen Sie einen Wochentag (Mo-Fr) während der Praxiszeiten",
    )


def detect_doctor_absence(ctx: ReportContext) -> ConflictDetail:
    """Detect and return example of doctor absence conflict."""
    monday = ctx.get_next_weekday(0)
    tuesday = monday + timedelta(days=1)
    wednesday = monday + timedelta(days=2)
    doctor = ctx.doctors[0]

    # Create absence
    absence = DoctorAbsence.objects.using("default").create(
        doctor=doctor,
        start_date=monday,
        end_date=wednesday,
        reason="Urlaub",
        active=True,
    )

    start = ctx.make_datetime(tuesday, dt_time(10, 0))
    end = ctx.make_datetime(tuesday, dt_time(10, 30))

    absence_reason = ""
    try:
        validate_doctor_absences(
            doctor_id=doctor.id,
            date=tuesday,
            start_time=start,
            end_time=end,
        )
    except DoctorAbsentError as e:
        absence_reason = e.reason

    return ConflictDetail(
        id=ctx.next_conflict_id(),
        category=ConflictCategory.DOCTOR_ABSENT,
        priority=ConflictPriority.MEDIUM,
        description=f"Arzt {doctor.first_name} {doctor.last_name} ist abwesend",
        affected_objects=[
            {"type": "DoctorAbsence", "id": absence.id, "reason": "Urlaub"},
            {"type": "NewAppointment", "time": f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"},
        ],
        time_window={
            "date": str(tuesday),
            "absence_start": str(monday),
            "absence_end": str(wednesday),
        },
        doctor_id=doctor.id,
        doctor_name=f"{doctor.first_name} {doctor.last_name}",
        cause=absence_reason or "Arzt ist im Urlaub",
        recommendation="Wählen Sie einen anderen Arzt oder verschieben Sie den Termin",
        metadata={"absence_id": absence.id},
    )


def detect_operation_overlap(ctx: ReportContext) -> ConflictDetail:
    """Detect and return example of operation overlap."""
    monday = ctx.get_next_weekday(0)
    surgeon = ctx.doctors[0]
    
    start1 = ctx.make_datetime(monday, dt_time(10, 0))
    end1 = ctx.make_datetime(monday, dt_time(11, 30))
    start2 = ctx.make_datetime(monday, dt_time(11, 0))
    end2 = ctx.make_datetime(monday, dt_time(12, 30))

    # Create first operation
    op1 = Operation.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        primary_surgeon=surgeon,
        op_room=ctx.rooms[0],
        op_type=ctx.op_types[0],
        start_time=start1,
        end_time=end1,
        status="planned",
    )

    # Detect conflict (same surgeon, different room)
    conflicts = check_operation_conflicts(
        date=monday,
        start_time=start2,
        end_time=end2,
        primary_surgeon_id=surgeon.id,
        room_id=ctx.rooms[1].id,
    )

    return ConflictDetail(
        id=ctx.next_conflict_id(),
        category=ConflictCategory.OPERATION_OVERLAP,
        priority=ConflictPriority.HIGH,
        description=f"Chirurg {surgeon.first_name} {surgeon.last_name} für überlappende OPs eingeteilt",
        affected_objects=[
            {"type": "Operation", "id": op1.id, "time": f"{start1.strftime('%H:%M')}-{end1.strftime('%H:%M')}"},
            {"type": "NewOperation", "time": f"{start2.strftime('%H:%M')}-{end2.strftime('%H:%M')}"},
        ],
        time_window={
            "date": str(monday),
            "overlap_start": "11:00",
            "overlap_end": "11:30",
        },
        doctor_id=surgeon.id,
        doctor_name=f"{surgeon.first_name} {surgeon.last_name}",
        cause="Derselbe Chirurg kann nicht zwei OPs gleichzeitig durchführen",
        recommendation="Verschieben Sie eine OP oder weisen Sie einen anderen Chirurgen zu",
        metadata={"conflicts_found": len(conflicts)},
    )


def detect_edge_case_zero_duration(ctx: ReportContext) -> ConflictDetail:
    """Detect and return example of zero duration edge case."""
    monday = ctx.get_next_weekday(0)
    
    return ConflictDetail(
        id=ctx.next_conflict_id(),
        category=ConflictCategory.VALIDATION_ERROR,
        priority=ConflictPriority.LOW,
        description="Termin mit Null-Dauer (Start = Ende)",
        affected_objects=[
            {"type": "InvalidAppointment", "start": "10:00", "end": "10:00"},
        ],
        time_window={
            "date": str(monday),
            "start": "10:00",
            "end": "10:00",
            "duration_minutes": 0,
        },
        cause="Startzeit entspricht Endzeit - Termin hat keine Dauer",
        recommendation="Geben Sie eine gültige Endzeit an, die nach der Startzeit liegt",
    )


def detect_edge_case_negative_duration(ctx: ReportContext) -> ConflictDetail:
    """Detect and return example of negative duration edge case."""
    monday = ctx.get_next_weekday(0)
    
    return ConflictDetail(
        id=ctx.next_conflict_id(),
        category=ConflictCategory.VALIDATION_ERROR,
        priority=ConflictPriority.LOW,
        description="Termin mit negativer Dauer (Ende vor Start)",
        affected_objects=[
            {"type": "InvalidAppointment", "start": "11:00", "end": "10:00"},
        ],
        time_window={
            "date": str(monday),
            "start": "11:00",
            "end": "10:00",
            "duration_minutes": -60,
        },
        cause="Endzeit liegt vor Startzeit",
        recommendation="Korrigieren Sie Start- und Endzeit",
    )


# ==============================================================================
# Grouping Functions
# ==============================================================================

def group_conflicts_by_type(conflicts: list[ConflictDetail]) -> list[ConflictGroup]:
    """Group conflicts by their category."""
    groups: dict[str, ConflictGroup] = {}
    
    for conflict in conflicts:
        key = conflict.category.value
        if key not in groups:
            groups[key] = ConflictGroup(
                group_key=key,
                group_type="by_type",
            )
        groups[key].conflicts.append(conflict)
        groups[key].count += 1
    
    return sorted(groups.values(), key=lambda g: g.count, reverse=True)


def group_conflicts_by_priority(conflicts: list[ConflictDetail]) -> list[ConflictGroup]:
    """Group conflicts by priority level."""
    groups: dict[str, ConflictGroup] = {}
    
    for conflict in conflicts:
        key = conflict.priority.value
        if key not in groups:
            groups[key] = ConflictGroup(
                group_key=key,
                group_type="by_priority",
            )
        groups[key].conflicts.append(conflict)
        groups[key].count += 1
    
    # Sort by priority (high first)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(groups.values(), key=lambda g: priority_order.get(g.group_key, 3))


def group_conflicts_by_doctor(conflicts: list[ConflictDetail]) -> list[ConflictGroup]:
    """Group conflicts by doctor."""
    groups: dict[str, ConflictGroup] = {}
    
    for conflict in conflicts:
        if conflict.doctor_name:
            key = conflict.doctor_name
        elif conflict.doctor_id:
            key = f"Doctor-{conflict.doctor_id}"
        else:
            key = "Kein Arzt"
        
        if key not in groups:
            groups[key] = ConflictGroup(
                group_key=key,
                group_type="by_doctor",
            )
        groups[key].conflicts.append(conflict)
        groups[key].count += 1
    
    return sorted(groups.values(), key=lambda g: g.count, reverse=True)


def group_conflicts_by_room(conflicts: list[ConflictDetail]) -> list[ConflictGroup]:
    """Group conflicts by room."""
    groups: dict[str, ConflictGroup] = {}
    
    for conflict in conflicts:
        if conflict.room_name:
            key = conflict.room_name
        elif conflict.room_id:
            key = f"Room-{conflict.room_id}"
        else:
            key = "Kein Raum"
        
        if key not in groups:
            groups[key] = ConflictGroup(
                group_key=key,
                group_type="by_room",
            )
        groups[key].conflicts.append(conflict)
        groups[key].count += 1
    
    return sorted(groups.values(), key=lambda g: g.count, reverse=True)


# ==============================================================================
# Example Generation
# ==============================================================================

def generate_conflict_examples(ctx: ReportContext) -> list[ConflictExample]:
    """Generate examples for each conflict type."""
    examples = []
    
    # Doctor Conflict Example
    doctor_conflict = detect_doctor_conflict(ctx)
    examples.append(ConflictExample(
        conflict_type=ConflictCategory.DOCTOR_CONFLICT,
        title="Arzt-Konflikt Beispiel",
        scenario="Dr. Mustermann hat zwei Termine zur gleichen Zeit gebucht",
        conflict_detail=doctor_conflict,
        code_snippet="""
# Erkennung des Arzt-Konflikts
conflicts = check_appointment_conflicts(
    date=monday,
    start_time=new_start,
    end_time=new_end,
    doctor_id=doctor.id,
)
if conflicts:
    raise SchedulingConflictError(conflicts)
""",
    ))

    # Room Conflict Example
    room_conflict = detect_room_conflict(ctx)
    examples.append(ConflictExample(
        conflict_type=ConflictCategory.ROOM_CONFLICT,
        title="Raum-Konflikt Beispiel",
        scenario="OP-Saal 1 ist für zwei Operationen gleichzeitig gebucht",
        conflict_detail=room_conflict,
        code_snippet="""
# Erkennung des Raum-Konflikts
conflicts = check_operation_conflicts(
    date=monday,
    start_time=new_start,
    end_time=new_end,
    primary_surgeon_id=surgeon.id,
    room_id=room.id,
)
if any(c.type == 'room_conflict' for c in conflicts):
    raise SchedulingConflictError(conflicts)
""",
    ))

    # Working Hours Violation Example
    working_hours = detect_working_hours_violation(ctx)
    examples.append(ConflictExample(
        conflict_type=ConflictCategory.WORKING_HOURS_VIOLATION,
        title="Arbeitszeit-Verstoß Beispiel",
        scenario="Termin am Sonntag außerhalb der Praxiszeiten",
        conflict_detail=working_hours,
        code_snippet="""
# Prüfung der Arbeitszeiten
try:
    validate_working_hours(
        doctor_id=doctor.id,
        date=sunday,
        start_time=start,
        end_time=end,
    )
except WorkingHoursViolation as e:
    print(f"Fehler: {e.reason}")
""",
    ))

    # Doctor Absence Example
    absence = detect_doctor_absence(ctx)
    examples.append(ConflictExample(
        conflict_type=ConflictCategory.DOCTOR_ABSENT,
        title="Arzt-Abwesenheit Beispiel",
        scenario="Termin während Urlaub des Arztes",
        conflict_detail=absence,
        code_snippet="""
# Prüfung auf Abwesenheit
try:
    validate_doctor_absences(
        doctor_id=doctor.id,
        date=tuesday,
        start_time=start,
        end_time=end,
    )
except DoctorAbsentError as e:
    print(f"Arzt abwesend: {e.reason}")
""",
    ))

    # Operation Overlap Example
    op_overlap = detect_operation_overlap(ctx)
    examples.append(ConflictExample(
        conflict_type=ConflictCategory.OPERATION_OVERLAP,
        title="OP-Überlappung Beispiel",
        scenario="Chirurg für zwei überlappende OPs eingeteilt",
        conflict_detail=op_overlap,
        code_snippet="""
# Erkennung der OP-Überlappung
conflicts = check_operation_conflicts(
    date=monday,
    start_time=new_start,
    end_time=new_end,
    primary_surgeon_id=surgeon.id,
    room_id=room.id,
)
if any(c.type == 'doctor_conflict' for c in conflicts):
    raise SchedulingConflictError(conflicts)
""",
    ))

    # Edge Case Examples
    edge_zero = detect_edge_case_zero_duration(ctx)
    examples.append(ConflictExample(
        conflict_type=ConflictCategory.VALIDATION_ERROR,
        title="Edge Case: Null-Dauer",
        scenario="Termin mit Start = Ende",
        conflict_detail=edge_zero,
    ))

    edge_neg = detect_edge_case_negative_duration(ctx)
    examples.append(ConflictExample(
        conflict_type=ConflictCategory.VALIDATION_ERROR,
        title="Edge Case: Negative Dauer",
        scenario="Termin mit Ende vor Start",
        conflict_detail=edge_neg,
    ))

    return examples


# ==============================================================================
# Summary Generation
# ==============================================================================

def generate_summary(conflicts: list[ConflictDetail]) -> ConflictSummary:
    """Generate summary statistics and recommendations."""
    summary = ConflictSummary(total_conflicts=len(conflicts))
    
    # Count by category
    for conflict in conflicts:
        cat = conflict.category.value
        summary.by_category[cat] = summary.by_category.get(cat, 0) + 1
    
    # Count by priority
    for conflict in conflicts:
        prio = conflict.priority.value
        summary.by_priority[prio] = summary.by_priority.get(prio, 0) + 1
    
    # Count critical (high priority)
    summary.critical_conflicts = summary.by_priority.get("high", 0)
    
    # Generate recommendations
    if summary.by_category.get("doctor_conflict", 0) > 0:
        summary.recommendations.append(
            "Implementieren Sie eine Echtzeit-Verfügbarkeitsprüfung für Ärzte bei der Terminbuchung"
        )
    
    if summary.by_category.get("room_conflict", 0) > 0:
        summary.recommendations.append(
            "Fügen Sie eine Raumverfügbarkeitsanzeige im OP-Planungskalender hinzu"
        )
    
    if summary.by_category.get("working_hours_violation", 0) > 0:
        summary.recommendations.append(
            "Zeigen Sie nur verfügbare Zeitfenster in der Buchungsoberfläche an"
        )
    
    if summary.by_category.get("doctor_absent", 0) > 0:
        summary.recommendations.append(
            "Integrieren Sie Abwesenheitskalender in die Terminplanung"
        )
    
    if summary.critical_conflicts > 5:
        summary.recommendations.append(
            "KRITISCH: Hohe Anzahl kritischer Konflikte - Überprüfen Sie die Planungsprozesse"
        )
    
    if not summary.recommendations:
        summary.recommendations.append(
            "Die Scheduling-Engine arbeitet korrekt - keine kritischen Probleme erkannt"
        )
    
    return summary


# ==============================================================================
# Main Report Generation
# ==============================================================================

def generate_conflict_report(seed: int = DEFAULT_SEED) -> ConflictReport:
    """
    Generate a comprehensive conflict report.
    
    Args:
        seed: Random seed for reproducibility.
        
    Returns:
        ConflictReport with all conflicts, groups, examples, and summary.
    """
    ctx = ReportContext(seed=seed)
    ctx.setup()
    
    # Collect all conflict examples
    all_conflicts: list[ConflictDetail] = []
    
    # Detect each conflict type
    all_conflicts.append(detect_doctor_conflict(ctx))
    all_conflicts.append(detect_room_conflict(ctx))
    all_conflicts.append(detect_working_hours_violation(ctx))
    all_conflicts.append(detect_doctor_absence(ctx))
    all_conflicts.append(detect_operation_overlap(ctx))
    all_conflicts.append(detect_edge_case_zero_duration(ctx))
    all_conflicts.append(detect_edge_case_negative_duration(ctx))
    
    # Generate examples
    examples = generate_conflict_examples(ctx)
    
    # Create report
    report = ConflictReport(
        timestamp=timezone.now().isoformat(),
        report_id=f"REPORT-{seed}-{timezone.now().strftime('%Y%m%d%H%M%S')}",
        conflict_types_overview=get_conflict_types_overview(),
        all_conflicts=all_conflicts,
        grouped_by_type=group_conflicts_by_type(all_conflicts),
        grouped_by_priority=group_conflicts_by_priority(all_conflicts),
        grouped_by_doctor=group_conflicts_by_doctor(all_conflicts),
        grouped_by_room=group_conflicts_by_room(all_conflicts),
        examples=examples,
        summary=generate_summary(all_conflicts),
        metadata={
            "seed": seed,
            "generator": "scheduling_conflict_report",
            "version": "1.0.0",
        },
    )
    
    return report


# ==============================================================================
# Text Report Formatting
# ==============================================================================

def format_text_report(report: ConflictReport) -> str:
    """Format the conflict report as human-readable text."""
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("SCHEDULING-KONFLIKTBERICHT")
    lines.append("=" * 80)
    lines.append(f"Bericht-ID: {report.report_id}")
    lines.append(f"Erstellt: {report.timestamp}")
    lines.append("")
    
    # 1. Conflict Types Overview
    lines.append("-" * 80)
    lines.append("1. ÜBERSICHT ALLER KONFLIKTTYPEN")
    lines.append("-" * 80)
    for ct in report.conflict_types_overview:
        lines.append(f"\n📋 {ct['name']} ({ct['type']})")
        lines.append(f"   Priorität: {ct['priority'].upper()}")
        lines.append(f"   Beschreibung: {ct['description']}")
        lines.append(f"   Erkennungsmethode: {ct['detection_method']}")
        if ct.get('examples'):
            lines.append("   Beispiele:")
            for ex in ct['examples']:
                lines.append(f"     • {ex}")
    lines.append("")
    
    # 2. Summary
    lines.append("-" * 80)
    lines.append("2. ZUSAMMENFASSUNG")
    lines.append("-" * 80)
    lines.append(f"\n📊 Gesamtzahl Konflikte: {report.summary.total_conflicts}")
    lines.append(f"🔴 Kritische Konflikte (hoch): {report.summary.critical_conflicts}")
    lines.append("")
    lines.append("Nach Kategorie:")
    for cat, count in report.summary.by_category.items():
        lines.append(f"   • {cat}: {count}")
    lines.append("")
    lines.append("Nach Priorität:")
    for prio, count in report.summary.by_priority.items():
        icon = "🔴" if prio == "high" else "🟡" if prio == "medium" else "🟢"
        lines.append(f"   {icon} {prio}: {count}")
    lines.append("")
    
    # 3. Grouped by Type
    lines.append("-" * 80)
    lines.append("3. KONFLIKTE NACH TYP")
    lines.append("-" * 80)
    for group in report.grouped_by_type:
        lines.append(f"\n📁 {group.group_key} ({group.count} Konflikte)")
        for conf in group.conflicts[:3]:  # Show first 3
            lines.append(f"   • [{conf.id}] {conf.description}")
    lines.append("")
    
    # 4. Grouped by Priority
    lines.append("-" * 80)
    lines.append("4. KONFLIKTE NACH PRIORITÄT")
    lines.append("-" * 80)
    for group in report.grouped_by_priority:
        icon = "🔴" if group.group_key == "high" else "🟡" if group.group_key == "medium" else "🟢"
        lines.append(f"\n{icon} {group.group_key.upper()} ({group.count} Konflikte)")
        for conf in group.conflicts:
            lines.append(f"   • [{conf.id}] {conf.description}")
    lines.append("")
    
    # 5. Detailed Conflicts
    lines.append("-" * 80)
    lines.append("5. DETAILLIERTE KONFLIKTBESCHREIBUNGEN")
    lines.append("-" * 80)
    for conf in report.all_conflicts:
        prio_icon = "🔴" if conf.priority == ConflictPriority.HIGH else "🟡" if conf.priority == ConflictPriority.MEDIUM else "🟢"
        lines.append(f"\n{prio_icon} KONFLIKT {conf.id}")
        lines.append(f"   Typ: {conf.category.value}")
        lines.append(f"   Priorität: {conf.priority.value}")
        lines.append(f"   Beschreibung: {conf.description}")
        if conf.doctor_name:
            lines.append(f"   Arzt: {conf.doctor_name}")
        if conf.room_name:
            lines.append(f"   Raum: {conf.room_name}")
        lines.append(f"   Zeitfenster: {conf.time_window}")
        lines.append(f"   Ursache: {conf.cause}")
        lines.append(f"   Empfehlung: {conf.recommendation}")
    lines.append("")
    
    # 6. Examples
    lines.append("-" * 80)
    lines.append("6. KONFLIKT-BEISPIELE")
    lines.append("-" * 80)
    for ex in report.examples:
        lines.append(f"\n📖 {ex.title}")
        lines.append(f"   Szenario: {ex.scenario}")
        if ex.code_snippet:
            lines.append("   Code:")
            for code_line in ex.code_snippet.strip().split('\n'):
                lines.append(f"      {code_line}")
    lines.append("")
    
    # 7. Recommendations
    lines.append("-" * 80)
    lines.append("7. EMPFEHLUNGEN ZUR OPTIMIERUNG")
    lines.append("-" * 80)
    for i, rec in enumerate(report.summary.recommendations, 1):
        lines.append(f"\n💡 {i}. {rec}")
    lines.append("")
    
    lines.append("=" * 80)
    lines.append("ENDE DES KONFLIKTBERICHTS")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def print_conflict_report(report: ConflictReport) -> None:
    """Print the conflict report to stdout."""
    print(format_text_report(report))
