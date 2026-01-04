"""
Scheduling-specific exceptions for the appointments app.

These exceptions are raised by the scheduling services and should be
translated to appropriate DRF responses in the views.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Conflict:
    """Represents a single scheduling conflict."""
    type: str  # 'doctor_conflict', 'room_conflict', 'device_conflict', 'patient_conflict'
    model: str  # 'Appointment' or 'Operation'
    id: int | None = None
    resource_id: int | None = None
    message: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {
            'type': self.type,
            'model': self.model,
        }
        if self.id is not None:
            result['id'] = self.id
        if self.resource_id is not None:
            result['resource_id'] = self.resource_id
        if self.message:
            result['message'] = self.message
        if self.meta:
            result['meta'] = self.meta
        return result


class SchedulingError(Exception):
    """Base exception for all scheduling-related errors."""
    pass


class SchedulingConflictError(SchedulingError):
    """
    Raised when scheduling conflicts are detected.
    
    Contains a list of Conflict objects describing each conflict found.
    """
    def __init__(self, conflicts: list[Conflict], message: str = "Scheduling conflicts detected"):
        self.conflicts = conflicts
        self.message = message
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            'detail': self.message,
            'conflicts': [c.to_dict() for c in self.conflicts],
        }


class WorkingHoursViolation(SchedulingError):
    """
    Raised when a scheduling request falls outside working hours.
    
    Attributes:
        doctor_id: The ID of the doctor
        date: The date in question
        start_time: Requested start time
        end_time: Requested end time
        reason: Specific reason ('no_practice_hours', 'no_doctor_hours', 'outside_practice', 'outside_doctor')
        alternatives: Optional list of alternative suggestions
    """
    def __init__(
        self,
        *,
        doctor_id: int,
        date: str,
        start_time: str,
        end_time: str,
        reason: str,
        message: str = "Requested time is outside working hours",
        alternatives: list[dict] | None = None,
    ):
        self.doctor_id = doctor_id
        self.date = date
        self.start_time = start_time
        self.end_time = end_time
        self.reason = reason
        self.alternatives = alternatives or []
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        result = {
            'detail': str(self),
            'reason': self.reason,
            'doctor_id': self.doctor_id,
            'date': self.date,
            'start_time': self.start_time,
            'end_time': self.end_time,
        }
        if self.alternatives:
            result['alternatives'] = self.alternatives
        return result


class DoctorAbsentError(SchedulingError):
    """
    Raised when a doctor is absent on the requested date.
    
    Attributes:
        doctor_id: The ID of the doctor
        date: The date when the doctor is absent
        absence_id: The ID of the DoctorAbsence record
        reason: The reason for the absence (if provided)
        alternatives: Optional list of alternative suggestions
    """
    def __init__(
        self,
        *,
        doctor_id: int,
        date: str,
        absence_id: int | None = None,
        reason: str | None = None,
        message: str = "Doctor is absent on the requested date",
        alternatives: list[dict] | None = None,
    ):
        self.doctor_id = doctor_id
        self.date = date
        self.absence_id = absence_id
        self.reason = reason
        self.alternatives = alternatives or []
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        result = {
            'detail': str(self),
            'doctor_id': self.doctor_id,
            'date': self.date,
        }
        if self.absence_id is not None:
            result['absence_id'] = self.absence_id
        if self.reason:
            result['reason'] = self.reason
        if self.alternatives:
            result['alternatives'] = self.alternatives
        return result


class DoctorBreakConflict(SchedulingError):
    """
    Raised when a scheduling request overlaps with a doctor break.
    
    Attributes:
        doctor_id: The ID of the doctor (None if practice-wide break)
        date: The date of the break
        break_id: The ID of the DoctorBreak record
        break_start: Start time of the break
        break_end: End time of the break
    """
    def __init__(
        self,
        *,
        doctor_id: int | None,
        date: str,
        break_id: int,
        break_start: str,
        break_end: str,
        message: str = "Requested time overlaps with a break",
    ):
        self.doctor_id = doctor_id
        self.date = date
        self.break_id = break_id
        self.break_start = break_start
        self.break_end = break_end
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            'detail': str(self),
            'doctor_id': self.doctor_id,
            'date': self.date,
            'break_id': self.break_id,
            'break_start': self.break_start,
            'break_end': self.break_end,
        }


class InvalidSchedulingData(SchedulingError):
    """
    Raised when scheduling data is invalid (e.g., end_time before start_time).
    """
    def __init__(self, message: str, field: str | None = None):
        self.field = field
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        result = {'detail': str(self)}
        if self.field:
            result['field'] = self.field
        return result
