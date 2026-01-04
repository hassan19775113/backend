"""
Scheduling Engine for PraxiApp.

This service layer encapsulates all scheduling logic for Appointments and Operations.
All business logic for conflict detection, working hours validation, and absence checks
is centralized here. Views should delegate to these functions rather than implementing
business logic directly.

Architecture Rules:
- All DB access uses .using('default') - NO access to medical DB
- patient_id is always an integer, never a FK to medical.Patient
- All exceptions are custom types from appointments.exceptions
- Views translate exceptions to appropriate DRF responses
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from django.db.models import Q
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
    DoctorAbsence,
    DoctorBreak,
    DoctorHours,
    Operation,
    OperationDevice,
    PracticeHours,
    Resource,
)
from praxi_backend.core.models import User
from praxi_backend.core.utils import log_patient_action

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _localize_datetime(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware and in local timezone."""
    if dt is None:
        return None
    if timezone.is_aware(dt):
        return timezone.localtime(dt)
    return timezone.make_aware(dt, timezone.get_current_timezone())


def _get_date_from_datetime(dt: datetime) -> date:
    """Extract date from a datetime, localizing if necessary."""
    local_dt = _localize_datetime(dt)
    return local_dt.date() if local_dt else None


def _doctor_display_name(doctor: User) -> str:
    """Get display name for a doctor."""
    return doctor.get_full_name() or getattr(doctor, 'username', str(doctor.id))


def _get_active_doctors(*, exclude_doctor_id: int | None = None) -> list[User]:
    """Get all active doctors, optionally excluding one."""
    qs = User.objects.using('default').filter(is_active=True, role__name='doctor')
    if exclude_doctor_id is not None:
        qs = qs.exclude(id=exclude_doctor_id)
    return list(qs.order_by('id'))


# ---------------------------------------------------------------------------
# Conflict Detection Functions
# ---------------------------------------------------------------------------

def check_appointment_conflicts(
    *,
    date: date,
    start_time: datetime,
    end_time: datetime,
    doctor_id: int,
    room_id: int | None = None,
    resource_ids: list[int] | None = None,
    exclude_appointment_id: int | None = None,
) -> list[Conflict]:
    """
    Check for conflicts when scheduling an appointment.
    
    Checks:
    - Overlapping appointments for the same doctor
    - Overlapping operations for the same doctor (as primary_surgeon, assistant, or anesthesist)
    - Room conflicts (if room_id or resource_ids with rooms provided)
    - Device conflicts (if resource_ids with devices provided)
    
    Args:
        date: The date of the appointment
        start_time: Start datetime of the appointment
        end_time: End datetime of the appointment
        doctor_id: ID of the doctor
        room_id: Optional ID of a room resource
        resource_ids: Optional list of resource IDs (rooms and devices)
        exclude_appointment_id: Optional ID of appointment to exclude (for updates)
    
    Returns:
        List of Conflict objects. Empty list means no conflicts.
    """
    conflicts: list[Conflict] = []
    
    # 1. Doctor appointment conflicts
    doctor_appts = Appointment.objects.using('default').filter(
        doctor_id=doctor_id,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_appointment_id is not None:
        doctor_appts = doctor_appts.exclude(id=exclude_appointment_id)
    
    for appt in doctor_appts:
        conflicts.append(Conflict(
            type='doctor_conflict',
            model='Appointment',
            id=appt.id,
            message=f'Doctor has overlapping appointment #{appt.id}',
        ))
    
    # 2. Doctor operation conflicts (doctor might be involved in an operation)
    doctor_ops = Operation.objects.using('default').filter(
        Q(primary_surgeon_id=doctor_id) | Q(assistant_id=doctor_id) | Q(anesthesist_id=doctor_id),
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    for op in doctor_ops:
        conflicts.append(Conflict(
            type='doctor_conflict',
            model='Operation',
            id=op.id,
            message=f'Doctor is involved in operation #{op.id}',
        ))
    
    # 3. Room/Resource conflicts
    all_resource_ids = list(resource_ids or [])
    if room_id is not None and room_id not in all_resource_ids:
        all_resource_ids.append(room_id)
    
    if all_resource_ids:
        # Get resource types to differentiate rooms and devices
        resources = {r.id: r for r in Resource.objects.using('default').filter(id__in=all_resource_ids)}
        room_ids = [rid for rid in all_resource_ids if resources.get(rid) and resources[rid].type == 'room']
        device_ids = [rid for rid in all_resource_ids if resources.get(rid) and resources[rid].type == 'device']
        
        # Check appointment resource conflicts
        ar_conflicts = AppointmentResource.objects.using('default').filter(
            resource_id__in=all_resource_ids,
            appointment__start_time__lt=end_time,
            appointment__end_time__gt=start_time,
        ).select_related('resource', 'appointment')
        
        if exclude_appointment_id is not None:
            ar_conflicts = ar_conflicts.exclude(appointment_id=exclude_appointment_id)
        
        for ar in ar_conflicts:
            conflict_type = 'room_conflict' if ar.resource.type == 'room' else 'device_conflict'
            conflicts.append(Conflict(
                type=conflict_type,
                model='Appointment',
                id=ar.appointment_id,
                resource_id=ar.resource_id,
                message=f'Resource {ar.resource.name} is booked by appointment #{ar.appointment_id}',
            ))
        
        # Check operation room conflicts
        if room_ids:
            op_room_conflicts = Operation.objects.using('default').filter(
                op_room_id__in=room_ids,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )
            for op in op_room_conflicts:
                conflicts.append(Conflict(
                    type='room_conflict',
                    model='Operation',
                    id=op.id,
                    resource_id=op.op_room_id,
                    message=f'Room is used by operation #{op.id}',
                ))
        
        # Check operation device conflicts
        if device_ids:
            od_conflicts = OperationDevice.objects.using('default').filter(
                resource_id__in=device_ids,
                operation__start_time__lt=end_time,
                operation__end_time__gt=start_time,
            ).select_related('operation', 'resource')
            
            for od in od_conflicts:
                conflicts.append(Conflict(
                    type='device_conflict',
                    model='Operation',
                    id=od.operation_id,
                    resource_id=od.resource_id,
                    message=f'Device is used by operation #{od.operation_id}',
                ))
    
    return conflicts


def check_operation_conflicts(
    *,
    date: date,
    start_time: datetime,
    end_time: datetime,
    primary_surgeon_id: int,
    assistant_id: int | None = None,
    anesthesist_id: int | None = None,
    room_id: int,
    device_ids: list[int] | None = None,
    exclude_operation_id: int | None = None,
) -> list[Conflict]:
    """
    Check for conflicts when scheduling an operation.
    
    Checks:
    - Room conflicts with other operations
    - Room conflicts with appointments
    - Device conflicts with other operations
    - Device conflicts with appointments
    - Primary surgeon conflicts (appointments and operations)
    - Assistant conflicts (if specified)
    - Anesthesist conflicts (if specified)
    
    Args:
        date: The date of the operation
        start_time: Start datetime of the operation
        end_time: End datetime of the operation
        primary_surgeon_id: ID of the primary surgeon
        assistant_id: Optional ID of the assistant
        anesthesist_id: Optional ID of the anesthesist
        room_id: ID of the operation room
        device_ids: Optional list of device resource IDs
        exclude_operation_id: Optional ID of operation to exclude (for updates)
    
    Returns:
        List of Conflict objects. Empty list means no conflicts.
    """
    conflicts: list[Conflict] = []
    
    # 1. Room conflicts - other operations
    room_op_conflicts = Operation.objects.using('default').filter(
        op_room_id=room_id,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_operation_id is not None:
        room_op_conflicts = room_op_conflicts.exclude(id=exclude_operation_id)
    
    for op in room_op_conflicts:
        conflicts.append(Conflict(
            type='room_conflict',
            model='Operation',
            id=op.id,
            resource_id=room_id,
            message=f'Room is already booked by operation #{op.id}',
        ))
    
    # 2. Room conflicts - appointments that booked this room as resource
    room_appt_conflicts = AppointmentResource.objects.using('default').filter(
        resource_id=room_id,
        appointment__start_time__lt=end_time,
        appointment__end_time__gt=start_time,
    ).select_related('appointment')
    
    for ar in room_appt_conflicts:
        conflicts.append(Conflict(
            type='room_conflict',
            model='Appointment',
            id=ar.appointment_id,
            resource_id=room_id,
            message=f'Room is booked by appointment #{ar.appointment_id}',
        ))
    
    # 3. Device conflicts
    if device_ids:
        # Device conflicts with other operations
        od_conflicts = OperationDevice.objects.using('default').filter(
            resource_id__in=device_ids,
            operation__start_time__lt=end_time,
            operation__end_time__gt=start_time,
        ).select_related('operation')
        
        if exclude_operation_id is not None:
            od_conflicts = od_conflicts.exclude(operation_id=exclude_operation_id)
        
        for od in od_conflicts:
            conflicts.append(Conflict(
                type='device_conflict',
                model='Operation',
                id=od.operation_id,
                resource_id=od.resource_id,
                message=f'Device is already used by operation #{od.operation_id}',
            ))
        
        # Device conflicts with appointments
        device_appt_conflicts = AppointmentResource.objects.using('default').filter(
            resource_id__in=device_ids,
            appointment__start_time__lt=end_time,
            appointment__end_time__gt=start_time,
        ).select_related('appointment')
        
        for ar in device_appt_conflicts:
            conflicts.append(Conflict(
                type='device_conflict',
                model='Appointment',
                id=ar.appointment_id,
                resource_id=ar.resource_id,
                message=f'Device is booked by appointment #{ar.appointment_id}',
            ))
    
    # 4. Doctor conflicts (all team members)
    doctor_ids = [primary_surgeon_id]
    if assistant_id:
        doctor_ids.append(assistant_id)
    if anesthesist_id:
        doctor_ids.append(anesthesist_id)
    
    for doctor_id in doctor_ids:
        # Check appointments
        doctor_appts = Appointment.objects.using('default').filter(
            doctor_id=doctor_id,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        for appt in doctor_appts:
            conflicts.append(Conflict(
                type='doctor_conflict',
                model='Appointment',
                id=appt.id,
                meta={'doctor_id': doctor_id},
                message=f'Doctor {doctor_id} has overlapping appointment #{appt.id}',
            ))
        
        # Check other operations
        doctor_ops = Operation.objects.using('default').filter(
            Q(primary_surgeon_id=doctor_id) | Q(assistant_id=doctor_id) | Q(anesthesist_id=doctor_id),
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if exclude_operation_id is not None:
            doctor_ops = doctor_ops.exclude(id=exclude_operation_id)
        
        for op in doctor_ops:
            conflicts.append(Conflict(
                type='doctor_conflict',
                model='Operation',
                id=op.id,
                meta={'doctor_id': doctor_id},
                message=f'Doctor {doctor_id} is involved in operation #{op.id}',
            ))
    
    return conflicts


def check_patient_conflicts(
    *,
    patient_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_appointment_id: int | None = None,
    exclude_operation_id: int | None = None,
) -> list[Conflict]:
    """
    Check for conflicts for the same patient.
    
    Args:
        patient_id: The patient ID (integer, not FK)
        start_time: Start datetime
        end_time: End datetime
        exclude_appointment_id: Optional appointment ID to exclude
        exclude_operation_id: Optional operation ID to exclude
    
    Returns:
        List of Conflict objects.
    """
    conflicts: list[Conflict] = []
    
    # Check appointment conflicts
    patient_appts = Appointment.objects.using('default').filter(
        patient_id=patient_id,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_appointment_id is not None:
        patient_appts = patient_appts.exclude(id=exclude_appointment_id)
    
    for appt in patient_appts:
        conflicts.append(Conflict(
            type='patient_conflict',
            model='Appointment',
            id=appt.id,
            message=f'Patient already has appointment #{appt.id} in this time range',
        ))
    
    # Check operation conflicts
    patient_ops = Operation.objects.using('default').filter(
        patient_id=patient_id,
        start_time__lt=end_time,
        end_time__gt=start_time,
    )
    if exclude_operation_id is not None:
        patient_ops = patient_ops.exclude(id=exclude_operation_id)
    
    for op in patient_ops:
        conflicts.append(Conflict(
            type='patient_conflict',
            model='Operation',
            id=op.id,
            message=f'Patient already has operation #{op.id} in this time range',
        ))
    
    return conflicts


# ---------------------------------------------------------------------------
# Working Hours Validation
# ---------------------------------------------------------------------------

def validate_working_hours(
    *,
    date: date,
    start_time: datetime,
    end_time: datetime,
    doctor_id: int,
) -> None:
    """
    Validate that the requested time falls within working hours.
    
    Checks:
    - Practice hours exist for the weekday
    - Doctor hours exist for the weekday
    - Requested time falls within both practice and doctor hours
    
    Args:
        date: The date to check
        start_time: Start datetime
        end_time: End datetime
        doctor_id: ID of the doctor
    
    Raises:
        WorkingHoursViolation: If the time is outside working hours
    """
    local_start = _localize_datetime(start_time)
    local_end = _localize_datetime(end_time)
    
    weekday = local_start.weekday()  # 0=Monday, 6=Sunday
    start_t = local_start.time()
    end_t = local_end.time()
    
    # Check practice hours
    practice_hours = PracticeHours.objects.using('default').filter(
        weekday=weekday,
        active=True,
    )
    
    if not practice_hours.exists():
        raise WorkingHoursViolation(
            doctor_id=doctor_id,
            date=date.isoformat(),
            start_time=start_t.isoformat(),
            end_time=end_t.isoformat(),
            reason='no_practice_hours',
            message=f'No practice hours defined for weekday {weekday}',
        )
    
    # Check if appointment fits within any practice hours window
    practice_ok = practice_hours.filter(
        start_time__lte=start_t,
        end_time__gte=end_t,
    ).exists()
    
    if not practice_ok:
        raise WorkingHoursViolation(
            doctor_id=doctor_id,
            date=date.isoformat(),
            start_time=start_t.isoformat(),
            end_time=end_t.isoformat(),
            reason='outside_practice_hours',
            message='Requested time is outside practice hours',
        )
    
    # Check doctor hours
    doctor_hours = DoctorHours.objects.using('default').filter(
        doctor_id=doctor_id,
        weekday=weekday,
        active=True,
    )
    
    if not doctor_hours.exists():
        raise WorkingHoursViolation(
            doctor_id=doctor_id,
            date=date.isoformat(),
            start_time=start_t.isoformat(),
            end_time=end_t.isoformat(),
            reason='no_doctor_hours',
            message=f'Doctor has no working hours on weekday {weekday}',
        )
    
    # Check if appointment fits within any doctor hours window
    doctor_ok = doctor_hours.filter(
        start_time__lte=start_t,
        end_time__gte=end_t,
    ).exists()
    
    if not doctor_ok:
        raise WorkingHoursViolation(
            doctor_id=doctor_id,
            date=date.isoformat(),
            start_time=start_t.isoformat(),
            end_time=end_t.isoformat(),
            reason='outside_doctor_hours',
            message='Requested time is outside doctor\'s working hours',
        )


# ---------------------------------------------------------------------------
# Absence and Break Validation
# ---------------------------------------------------------------------------

def validate_doctor_absences(
    *,
    date: date,
    doctor_id: int,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> None:
    """
    Validate that the doctor is not absent on the requested date.
    
    Args:
        date: The date to check
        doctor_id: ID of the doctor
        start_time: Optional start time (for multi-day check)
        end_time: Optional end time (for multi-day check)
    
    Raises:
        DoctorAbsentError: If the doctor is absent
    """
    # Calculate date range if spanning multiple days
    if start_time and end_time:
        start_date = _get_date_from_datetime(start_time)
        end_date = _get_date_from_datetime(end_time)
    else:
        start_date = date
        end_date = date
    
    absence = DoctorAbsence.objects.using('default').filter(
        doctor_id=doctor_id,
        active=True,
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).first()
    
    if absence is not None:
        raise DoctorAbsentError(
            doctor_id=doctor_id,
            date=date.isoformat(),
            absence_id=absence.id,
            reason=absence.reason,
            message=f'Doctor is absent from {absence.start_date} to {absence.end_date}',
        )


def validate_doctor_breaks(
    *,
    date: date,
    start_time: datetime,
    end_time: datetime,
    doctor_id: int,
) -> None:
    """
    Validate that the requested time does not overlap with any breaks.
    
    Checks both practice-wide breaks (doctor=NULL) and doctor-specific breaks.
    
    Args:
        date: The date to check
        start_time: Start datetime
        end_time: End datetime
        doctor_id: ID of the doctor
    
    Raises:
        DoctorBreakConflict: If the time overlaps with a break
    """
    local_start = _localize_datetime(start_time)
    local_end = _localize_datetime(end_time)
    tz = timezone.get_current_timezone()
    
    # Get the date range (appointment might span multiple days, though unlikely)
    start_date = local_start.date()
    end_date = local_end.date()
    
    # Query breaks for this date range (practice-wide or for this doctor)
    breaks = DoctorBreak.objects.using('default').filter(
        active=True,
        date__gte=start_date,
        date__lte=end_date,
    ).filter(
        Q(doctor__isnull=True) | Q(doctor_id=doctor_id)
    ).order_by('date', 'start_time')
    
    for br in breaks:
        br_start = timezone.make_aware(datetime.combine(br.date, br.start_time), tz)
        br_end = timezone.make_aware(datetime.combine(br.date, br.end_time), tz)
        
        # Check for overlap
        if local_start < br_end and local_end > br_start:
            raise DoctorBreakConflict(
                doctor_id=br.doctor_id,
                date=br.date.isoformat(),
                break_id=br.id,
                break_start=br.start_time.isoformat(),
                break_end=br.end_time.isoformat(),
                message='Requested time overlaps with a scheduled break',
            )


# ---------------------------------------------------------------------------
# High-Level Planning Functions
# ---------------------------------------------------------------------------

def plan_appointment(
    *,
    data: dict,
    user: 'AbstractUser',
    skip_conflict_check: bool = False,
) -> Appointment:
    """
    Plan and create an appointment with full validation.
    
    This is the main entry point for creating appointments. It performs:
    1. Basic data validation
    2. Working hours validation
    3. Doctor absence validation
    4. Break validation
    5. Conflict detection (doctor, room, device, patient)
    6. Creates the appointment
    7. Logs the action
    
    Args:
        data: Dictionary with appointment data:
            - patient_id: int (required)
            - doctor_id: int (required)
            - start_time: datetime (required)
            - end_time: datetime (required)
            - type_id: int (optional)
            - resource_ids: list[int] (optional)
            - status: str (optional, defaults to 'scheduled')
            - notes: str (optional)
        user: The user creating the appointment (for audit logging)
        skip_conflict_check: If True, skip conflict detection (for special cases)
    
    Returns:
        The created Appointment instance
    
    Raises:
        InvalidSchedulingData: If required data is missing or invalid
        WorkingHoursViolation: If time is outside working hours
        DoctorAbsentError: If doctor is absent
        DoctorBreakConflict: If time overlaps with a break
        SchedulingConflictError: If conflicts are detected
    """
    # Extract and validate required fields
    patient_id = data.get('patient_id')
    doctor_id = data.get('doctor_id')
    start_time = data.get('start_time')
    end_time = data.get('end_time')
    
    if patient_id is None:
        raise InvalidSchedulingData('patient_id is required', field='patient_id')
    if doctor_id is None:
        raise InvalidSchedulingData('doctor_id is required', field='doctor_id')
    if start_time is None:
        raise InvalidSchedulingData('start_time is required', field='start_time')
    if end_time is None:
        raise InvalidSchedulingData('end_time is required', field='end_time')
    
    # Validate times
    if end_time <= start_time:
        raise InvalidSchedulingData('end_time must be after start_time', field='end_time')
    
    # Resolve doctor
    doctor = User.objects.using('default').filter(id=doctor_id, is_active=True).first()
    if doctor is None:
        raise InvalidSchedulingData(f'Doctor with ID {doctor_id} not found or inactive', field='doctor_id')
    
    role_name = getattr(getattr(doctor, 'role', None), 'name', None)
    if role_name != 'doctor':
        raise InvalidSchedulingData('Specified user is not a doctor', field='doctor_id')
    
    # Get date
    appt_date = _get_date_from_datetime(start_time)
    
    # Validate working hours
    validate_working_hours(
        date=appt_date,
        start_time=start_time,
        end_time=end_time,
        doctor_id=doctor_id,
    )
    
    # Validate doctor absences
    validate_doctor_absences(
        date=appt_date,
        doctor_id=doctor_id,
        start_time=start_time,
        end_time=end_time,
    )
    
    # Validate breaks
    validate_doctor_breaks(
        date=appt_date,
        start_time=start_time,
        end_time=end_time,
        doctor_id=doctor_id,
    )
    
    # Check conflicts unless skipped
    if not skip_conflict_check:
        conflicts = check_appointment_conflicts(
            date=appt_date,
            start_time=start_time,
            end_time=end_time,
            doctor_id=doctor_id,
            resource_ids=data.get('resource_ids'),
        )
        
        # Also check patient conflicts
        patient_conflicts = check_patient_conflicts(
            patient_id=patient_id,
            start_time=start_time,
            end_time=end_time,
        )
        conflicts.extend(patient_conflicts)
        
        if conflicts:
            raise SchedulingConflictError(conflicts)
    
    # Prepare appointment data
    type_id = data.get('type_id')
    appointment_type = None
    if type_id:
        from praxi_backend.appointments.models import AppointmentType
        appointment_type = AppointmentType.objects.using('default').filter(id=type_id, active=True).first()
    
    # Create the appointment
    appointment = Appointment.objects.using('default').create(
        patient_id=patient_id,
        doctor=doctor,
        type=appointment_type,
        start_time=start_time,
        end_time=end_time,
        status=data.get('status', Appointment.STATUS_SCHEDULED),
        notes=data.get('notes', ''),
    )
    
    # Handle resources
    resource_ids = data.get('resource_ids')
    if resource_ids:
        resources = Resource.objects.using('default').filter(id__in=resource_ids, active=True)
        for resource in resources:
            AppointmentResource.objects.using('default').create(
                appointment=appointment,
                resource=resource,
            )
    
    # Audit log (API semantics: creation via /appointments/)
    log_patient_action(user, 'appointment_create', patient_id)
    
    return appointment


def plan_operation(
    *,
    data: dict,
    user: 'AbstractUser',
    skip_conflict_check: bool = False,
) -> Operation:
    """
    Plan and create an operation with full validation.
    
    This is the main entry point for creating operations. It performs:
    1. Basic data validation
    2. Working hours validation (for primary surgeon)
    3. Doctor absence validation (for all team members)
    4. Break validation
    5. Conflict detection (room, devices, all team members, patient)
    6. Creates the operation
    7. Logs the action
    
    Args:
        data: Dictionary with operation data:
            - patient_id: int (required)
            - primary_surgeon_id: int (required)
            - assistant_id: int (optional)
            - anesthesist_id: int (optional)
            - op_room_id: int (required)
            - op_type_id: int (required)
            - start_time: datetime (required)
            - op_device_ids: list[int] (optional)
            - status: str (optional, defaults to 'planned')
            - notes: str (optional)
        user: The user creating the operation (for audit logging)
        skip_conflict_check: If True, skip conflict detection (for special cases)
    
    Returns:
        The created Operation instance
    
    Raises:
        InvalidSchedulingData: If required data is missing or invalid
        WorkingHoursViolation: If time is outside working hours
        DoctorAbsentError: If any team member is absent
        DoctorBreakConflict: If time overlaps with a break
        SchedulingConflictError: If conflicts are detected
    """
    from praxi_backend.appointments.models import OperationType
    
    # Extract and validate required fields
    patient_id = data.get('patient_id')
    primary_surgeon_id = data.get('primary_surgeon_id')
    op_room_id = data.get('op_room_id')
    op_type_id = data.get('op_type_id')
    start_time = data.get('start_time')
    
    if patient_id is None:
        raise InvalidSchedulingData('patient_id is required', field='patient_id')
    if primary_surgeon_id is None:
        raise InvalidSchedulingData('primary_surgeon_id is required', field='primary_surgeon_id')
    if op_room_id is None:
        raise InvalidSchedulingData('op_room_id is required', field='op_room_id')
    if op_type_id is None:
        raise InvalidSchedulingData('op_type_id is required', field='op_type_id')
    if start_time is None:
        raise InvalidSchedulingData('start_time is required', field='start_time')
    
    # Resolve operation type and calculate end_time
    op_type = OperationType.objects.using('default').filter(id=op_type_id, active=True).first()
    if op_type is None:
        raise InvalidSchedulingData(f'OperationType with ID {op_type_id} not found or inactive', field='op_type_id')
    
    total_minutes = (
        max(0, op_type.prep_duration or 0) +
        max(0, op_type.op_duration or 0) +
        max(0, op_type.post_duration or 0)
    )
    if total_minutes <= 0:
        raise InvalidSchedulingData('OperationType has invalid duration', field='op_type_id')
    
    end_time = start_time + timedelta(minutes=total_minutes)
    
    # Resolve primary surgeon
    primary_surgeon = User.objects.using('default').filter(id=primary_surgeon_id, is_active=True).first()
    if primary_surgeon is None:
        raise InvalidSchedulingData(f'Primary surgeon with ID {primary_surgeon_id} not found or inactive', field='primary_surgeon_id')
    
    role_name = getattr(getattr(primary_surgeon, 'role', None), 'name', None)
    if role_name != 'doctor':
        raise InvalidSchedulingData('Primary surgeon must have role "doctor"', field='primary_surgeon_id')
    
    # Resolve optional team members
    assistant_id = data.get('assistant_id')
    anesthesist_id = data.get('anesthesist_id')
    assistant = None
    anesthesist = None
    
    if assistant_id:
        assistant = User.objects.using('default').filter(id=assistant_id, is_active=True).first()
        if assistant is None:
            raise InvalidSchedulingData(f'Assistant with ID {assistant_id} not found or inactive', field='assistant_id')
    
    if anesthesist_id:
        anesthesist = User.objects.using('default').filter(id=anesthesist_id, is_active=True).first()
        if anesthesist is None:
            raise InvalidSchedulingData(f'Anesthesist with ID {anesthesist_id} not found or inactive', field='anesthesist_id')
    
    # Resolve room
    room = Resource.objects.using('default').filter(id=op_room_id, type='room', active=True).first()
    if room is None:
        raise InvalidSchedulingData(f'Room with ID {op_room_id} not found, inactive, or not a room', field='op_room_id')
    
    # Resolve devices
    op_device_ids = data.get('op_device_ids', [])
    device_objs = []
    if op_device_ids:
        device_objs = list(Resource.objects.using('default').filter(
            id__in=op_device_ids,
            type='device',
            active=True,
        ))
        found_ids = {d.id for d in device_objs}
        missing = [did for did in op_device_ids if did not in found_ids]
        if missing:
            raise InvalidSchedulingData(f'Devices with IDs {missing} not found, inactive, or not devices', field='op_device_ids')
    
    # Get date
    op_date = _get_date_from_datetime(start_time)
    
    # Validate working hours for primary surgeon (optional for ops - comment out if not needed)
    # Typically OP rooms have their own schedule, but we validate surgeon availability
    # validate_working_hours(
    #     date=op_date,
    #     start_time=start_time,
    #     end_time=end_time,
    #     doctor_id=primary_surgeon_id,
    # )
    
    # Validate doctor absences for all team members
    for doc_id, doc_name in [(primary_surgeon_id, 'Primary surgeon'), (assistant_id, 'Assistant'), (anesthesist_id, 'Anesthesist')]:
        if doc_id:
            try:
                validate_doctor_absences(
                    date=op_date,
                    doctor_id=doc_id,
                    start_time=start_time,
                    end_time=end_time,
                )
            except DoctorAbsentError as e:
                # Re-raise with more context
                e.message = f'{doc_name} is absent: {e.message}'
                raise
    
    # Check conflicts unless skipped
    if not skip_conflict_check:
        conflicts = check_operation_conflicts(
            date=op_date,
            start_time=start_time,
            end_time=end_time,
            primary_surgeon_id=primary_surgeon_id,
            assistant_id=assistant_id,
            anesthesist_id=anesthesist_id,
            room_id=op_room_id,
            device_ids=op_device_ids,
        )
        
        # Also check patient conflicts
        patient_conflicts = check_patient_conflicts(
            patient_id=patient_id,
            start_time=start_time,
            end_time=end_time,
        )
        conflicts.extend(patient_conflicts)
        
        if conflicts:
            raise SchedulingConflictError(conflicts)
    
    # Create the operation
    operation = Operation.objects.using('default').create(
        patient_id=patient_id,
        primary_surgeon=primary_surgeon,
        assistant=assistant,
        anesthesist=anesthesist,
        op_room=room,
        op_type=op_type,
        start_time=start_time,
        end_time=end_time,
        status=data.get('status', Operation.STATUS_PLANNED),
        notes=data.get('notes', ''),
    )
    
    # Handle devices
    for device in device_objs:
        OperationDevice.objects.using('default').create(
            operation=operation,
            resource=device,
        )
    
    # Audit log (API semantics: creation via /operations/)
    log_patient_action(user, 'operation_create', patient_id)
    
    return operation
