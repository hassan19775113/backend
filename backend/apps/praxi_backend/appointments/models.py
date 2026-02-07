"""Domain models for scheduling, operations and patient flow.

This module contains the core *managed* domain entities of PraxiApp.

Medical-domain note (critical):

- Patient master data lives in the managed ``praxi_backend.patients`` app.
- Appointments/operations still store an integer ``patient_id`` for simplicity and to
  avoid wide-ranging changes across the scheduling domain.

Architectural note:

- All ORM access for these models should use the ``default`` database alias.
        In production, the app runs on a single database.
"""

from datetime import date, timedelta

from django.conf import settings
from django.db import models


class AppointmentType(models.Model):
    """Configurable appointment category.

    Used for:
    - UI display (name/color)
    - Optional default duration (`duration_minutes`)
    - Enabling/disabling types without deleting historical data (`active`)
    """

    name = models.CharField(max_length=100, verbose_name="Name")
    color = models.CharField(
        max_length=7, blank=True, null=True, default="#2E8B57", verbose_name="Farbe"
    )
    duration_minutes = models.IntegerField(blank=True, null=True, verbose_name="Dauer (Minuten)")
    active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


class PracticeHours(models.Model):
    """Practice-wide opening hours.

    These hours represent when the practice is open/operational.
    Scheduling (suggestions and validations) requires that a time slot lies
    within practice hours *and* within the doctor's hours.
    """

    weekday = models.IntegerField(verbose_name="Wochentag")  # 0=Monday ... 6=Sunday
    start_time = models.TimeField(verbose_name="Startzeit")
    end_time = models.TimeField(verbose_name="Endzeit")
    active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ["weekday", "start_time", "id"]
        verbose_name = "Praxisöffnungszeit"
        verbose_name_plural = "Praxisöffnungszeiten"

    def __str__(self) -> str:
        return f"PracticeHours weekday={self.weekday} {self.start_time}-{self.end_time}"


class DoctorHours(models.Model):
    """Doctor-specific working hours.

    Medical meaning:
    - Defines when a doctor can see patients.
    - Used by scheduling validations to reject appointments outside availability.
    """

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_hours",
        verbose_name="Arzt",
    )
    weekday = models.IntegerField(verbose_name="Wochentag")
    start_time = models.TimeField(verbose_name="Startzeit")
    end_time = models.TimeField(verbose_name="Endzeit")
    active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ["doctor_id", "weekday", "start_time", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "weekday", "start_time", "end_time", "active"],
                name="uniq_doctorhours_slot_active",
            )
        ]
        verbose_name = "Arbeitszeit"
        verbose_name_plural = "Arbeitszeiten"

    def __str__(self) -> str:
        return f"DoctorHours doctor_id={self.doctor_id} weekday={self.weekday} {self.start_time}-{self.end_time}"


class DoctorAbsence(models.Model):
    """Doctor absence spanning a date range.

    Examples: vacation, sick leave, congress.
    If an appointment/operation overlaps any active absence date, scheduling
    should treat the doctor as unavailable.
    """

    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctor_absences",
        verbose_name="Arzt",
    )
    start_date = models.DateField(verbose_name="Startdatum")
    end_date = models.DateField(verbose_name="Enddatum")
    reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="Grund")
    duration_workdays = models.PositiveIntegerField(
        blank=True, null=True, verbose_name="Dauer (Werktage)"
    )
    remaining_days = models.PositiveIntegerField(
        blank=True, null=True, verbose_name="Verbleibend (Urlaubstage)"
    )
    return_date = models.DateField(blank=True, null=True, verbose_name="Arbeitet wieder ab")
    active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ["doctor_id", "start_date", "end_date", "id"]
        verbose_name = "Abwesenheit"
        verbose_name_plural = "Abwesenheiten"

    def __str__(self) -> str:
        return f"DoctorAbsence doctor_id={self.doctor_id} {self.start_date}-{self.end_date}"

    def _count_workdays(self, start_date, end_date):
        if start_date is None or end_date is None:
            return 0
        if end_date < start_date:
            return 0
        days = 0
        cur = start_date
        while cur <= end_date:
            if cur.weekday() < 5:
                days += 1
            cur += timedelta(days=1)
        return days

    def _next_workday(self, date_value):
        if date_value is None:
            return None
        cur = date_value + timedelta(days=1)
        while cur.weekday() >= 5:
            cur += timedelta(days=1)
        return cur

    def _calculate_remaining_days(self):
        if not self.doctor_id:
            return None
        if (self.reason or "").strip().lower() != "urlaub":
            return None
        year = self.start_date.year if self.start_date else None
        if year is None:
            return None
        allocation = getattr(self.doctor, "vacation_days_per_year", 30) or 0
        qs = DoctorAbsence.objects.using(self._state.db).filter(
            doctor_id=self.doctor_id,
            reason__iexact="Urlaub",
            active=True,
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        used = 0
        for absence in qs:
            if absence.start_date is None or absence.end_date is None:
                continue
            if absence.start_date.year > year or absence.end_date.year < year:
                continue
            start = max(absence.start_date, date(year, 1, 1))
            end = min(absence.end_date, date(year, 12, 31))
            used += self._count_workdays(start, end)
        used += self.duration_workdays or 0
        remaining = max(0, allocation - used)
        return remaining

    def save(self, *args, **kwargs):
        self.duration_workdays = self._count_workdays(self.start_date, self.end_date)
        self.return_date = self._next_workday(self.end_date)
        self.remaining_days = self._calculate_remaining_days()
        super().save(*args, **kwargs)


class DoctorBreak(models.Model):
    """Break/blocked time on a specific date.

    - If ``doctor`` is NULL: practice-wide break (e.g. team meeting).
    - If ``doctor`` is set: doctor-specific break.

    Used for fine-grained scheduling conflicts within a day.
    """

    # doctor=NULL => praxisweite Pause
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="doctor_breaks",
        verbose_name="Arzt",
    )
    date = models.DateField(verbose_name="Datum")
    start_time = models.TimeField(verbose_name="Startzeit")
    end_time = models.TimeField(verbose_name="Endzeit")
    reason = models.CharField(max_length=255, blank=True, null=True, verbose_name="Grund")
    active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ["date", "start_time", "doctor_id", "id"]
        verbose_name = "Pause"
        verbose_name_plural = "Pausen"

    def __str__(self) -> str:
        return f"DoctorBreak date={self.date} {self.start_time}-{self.end_time} doctor_id={self.doctor_id}"


class Appointment(models.Model):
    """A scheduled appointment in the practice.

    Medical meaning:
    - Represents an encounter slot (consultation/treatment) for a patient.
    - Can optionally consume resources (room/device) and has a responsible doctor.

    Technical notes:
    - ``patient_id`` stores the patient identifier (int). Patient master data lives
      in the managed `patients` table (same DB), but appointments keep an integer
      reference for compatibility.
    - ``resources`` is a M2M through ``AppointmentResource`` to support efficient
      constraints and unique pairing.
    """

    STATUS_SCHEDULED = "scheduled"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = (
        (STATUS_SCHEDULED, STATUS_SCHEDULED),
        (STATUS_CONFIRMED, STATUS_CONFIRMED),
        (STATUS_CANCELLED, STATUS_CANCELLED),
        (STATUS_COMPLETED, STATUS_COMPLETED),
    )

    id = models.AutoField(primary_key=True)
    patient_id = models.IntegerField(verbose_name="Patient-ID")
    type = models.ForeignKey(
        AppointmentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Terminart",
    )
    resources = models.ManyToManyField(
        "Resource",
        through="AppointmentResource",
        related_name="appointments",
        blank=True,
        verbose_name="Ressourcen",
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="Arzt",
    )
    start_time = models.DateTimeField(verbose_name="Startzeit")
    end_time = models.DateTimeField(verbose_name="Endzeit")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
        verbose_name="Status",
    )
    is_no_show = models.BooleanField(
        default=False,
        verbose_name="No-Show (bestaetigt)",
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Notizen")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ["-start_time", "-id"]
        verbose_name = "Termin"
        verbose_name_plural = "Termine"

    def __str__(self) -> str:
        return f"Appointment #{self.id} (patient_id={self.patient_id})"


class Resource(models.Model):
    """A schedulable resource.

    Types:
    - ``room``: physical room (e.g. treatment room, OP room)
    - ``device``: equipment shared across appointments/operations

    Resources can be used by both appointments and operations, and are considered
    by scheduling conflict checks.
    """

    TYPE_ROOM = "room"
    TYPE_DEVICE = "device"

    TYPE_CHOICES = (
        (TYPE_ROOM, TYPE_ROOM),
        (TYPE_DEVICE, TYPE_DEVICE),
    )

    name = models.CharField(max_length=255, verbose_name="Name")
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Typ")
    color = models.CharField(max_length=7, default="#6A5ACD", verbose_name="Farbe")
    active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ["type", "name", "id"]
        verbose_name = "Ressource"
        verbose_name_plural = "Ressourcen"

    def __str__(self) -> str:
        return f"{self.type}:{self.name}"


class AppointmentResource(models.Model):
    """Join table connecting appointments and resources.

    Uniqueness:
    - A resource can be attached at most once per appointment.
    """

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="appointment_resources",
        verbose_name="Termin",
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="appointment_resources",
        verbose_name="Ressource",
    )

    class Meta:
        unique_together = ("appointment", "resource")
        ordering = ["appointment_id", "resource_id", "id"]
        verbose_name = "Termin-Ressource"
        verbose_name_plural = "Termin-Ressourcen"


class OperationType(models.Model):
    """Configurable operation category.

    Durations are split into:
    - preparation (`prep_duration`)
    - operation (`op_duration`)
    - post-processing (`post_duration`)

    This supports schedule planning beyond a single "OP runtime".
    """

    name = models.CharField(max_length=255, verbose_name="Name")
    prep_duration = models.IntegerField(default=0, verbose_name="Vorbereitungsdauer (Minuten)")
    op_duration = models.IntegerField(default=0, verbose_name="OP-Dauer (Minuten)")
    post_duration = models.IntegerField(default=0, verbose_name="Nachbereitungsdauer (Minuten)")
    color = models.CharField(max_length=7, default="#8A2BE2", verbose_name="Farbe")
    active = models.BooleanField(default=True, verbose_name="Aktiv")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ["name", "id"]
        verbose_name = "OP-Typ"
        verbose_name_plural = "OP-Typen"

    def __str__(self) -> str:
        return self.name


class Operation(models.Model):
    """A scheduled operation (OP) for a patient.

    Medical meaning:
    - Represents a time window in which an operation (including prep/post) occurs.
    - Consumes an OP room and optional devices.
    - Has participating clinicians: primary surgeon, assistant, anesthesist.

    Technical notes:
    - ``patient_id`` stores the patient identifier (int). Patient master data lives
      in the managed `patients` table (same DB).
    - Device usage is represented via M2M through ``OperationDevice``.
    """

    STATUS_PLANNED = "planned"
    STATUS_CONFIRMED = "confirmed"
    STATUS_RUNNING = "running"
    STATUS_DONE = "done"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_PLANNED, STATUS_PLANNED),
        (STATUS_CONFIRMED, STATUS_CONFIRMED),
        (STATUS_RUNNING, STATUS_RUNNING),
        (STATUS_DONE, STATUS_DONE),
        (STATUS_CANCELLED, STATUS_CANCELLED),
    )

    # NOTE: We store the patient identifier as integer for compatibility.
    patient_id = models.IntegerField(verbose_name="Patient-ID")

    primary_surgeon = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="op_primary",
        on_delete=models.CASCADE,
        verbose_name="Hauptoperateur",
    )
    assistant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="op_assistant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Assistent",
    )
    anesthesist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="op_anesthesist",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Anästhesist",
    )

    op_room = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="operations_as_room",
        verbose_name="OP-Raum",
    )
    op_devices = models.ManyToManyField(
        Resource,
        through="OperationDevice",
        related_name="operations_as_device",
        blank=True,
        verbose_name="OP-Geräte",
    )
    op_type = models.ForeignKey(OperationType, on_delete=models.CASCADE, verbose_name="OP-Typ")

    start_time = models.DateTimeField(verbose_name="Startzeit")
    end_time = models.DateTimeField(verbose_name="Endzeit")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PLANNED, verbose_name="Status"
    )
    notes = models.TextField(blank=True, null=True, verbose_name="Notizen")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Aktualisiert am")

    class Meta:
        ordering = ["-start_time", "-id"]
        verbose_name = "Operation"
        verbose_name_plural = "Operationen"

    def __str__(self) -> str:
        return f"Operation #{self.id} (patient_id={self.patient_id})"


class OperationDevice(models.Model):
    """Join table connecting operations and device resources."""

    operation = models.ForeignKey(
        Operation,
        on_delete=models.CASCADE,
        related_name="operation_devices",
        verbose_name="Operation",
    )
    resource = models.ForeignKey(
        Resource,
        on_delete=models.CASCADE,
        related_name="operation_devices",
        verbose_name="Ressource",
    )

    class Meta:
        unique_together = ("operation", "resource")
        ordering = ["operation_id", "resource_id", "id"]
        verbose_name = "OP-Gerät"
        verbose_name_plural = "OP-Geräte"

    def __str__(self) -> str:
        resource_name = getattr(self.resource, "name", None)
        if resource_name:
            return resource_name
        return f"OP-Gerät #{self.id}"


class PatientFlow(models.Model):
    """Track the patient's journey/status through a visit or operation.

    Medical meaning:
    - Captures operational workflow states (arrival, waiting, preparation, treatment,
      recovery, done).

    Association:
    - A flow may be linked to an ``Appointment`` or an ``Operation``.
      (Both fields are nullable; domain logic should typically ensure exactly one.)
    """

    STATUS_REGISTERED = "registered"
    STATUS_WAITING = "waiting"
    STATUS_PREPARING = "preparing"
    STATUS_IN_TREATMENT = "in_treatment"
    STATUS_POST_TREATMENT = "post_treatment"
    STATUS_DONE = "done"

    STATUS_CHOICES = (
        (STATUS_REGISTERED, STATUS_REGISTERED),
        (STATUS_WAITING, STATUS_WAITING),
        (STATUS_PREPARING, STATUS_PREPARING),
        (STATUS_IN_TREATMENT, STATUS_IN_TREATMENT),
        (STATUS_POST_TREATMENT, STATUS_POST_TREATMENT),
        (STATUS_DONE, STATUS_DONE),
    )

    appointment = models.ForeignKey(
        Appointment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patient_flows",
        verbose_name="Termin",
    )
    operation = models.ForeignKey(
        Operation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="patient_flows",
        verbose_name="Operation",
    )
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_REGISTERED, verbose_name="Status"
    )
    arrival_time = models.DateTimeField(null=True, blank=True, verbose_name="Ankunftszeit")
    status_changed_at = models.DateTimeField(auto_now=True, verbose_name="Status geändert am")
    notes = models.TextField(null=True, blank=True, verbose_name="Notizen")

    class Meta:
        ordering = ["-status_changed_at", "-id"]
        verbose_name = "Patientenfluss"
        verbose_name_plural = "Patientenflüsse"

    def __str__(self) -> str:
        return f"PatientFlow #{self.id} ({self.status})"
