import random
from datetime import datetime, timedelta, time, date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from medical.models import Patient
from .models import (
    AppointmentType,
    PracticeHours,
    DoctorHours,
    DoctorAbsence,
    DoctorBreak,
    Resource,
    Appointment,
    OperationType,
    Operation,
    PatientFlow,
)

User = get_user_model()
RANDOM_SEED = 42


def seed_appointments(flush: bool = False) -> dict:
    """
    Seedet:
    - AppointmentType
    - PracticeHours
    - DoctorHours, DoctorAbsence, DoctorBreak
    - Resources
    - Appointments
    - OperationType, Operation
    - PatientFlow

    Wenn flush=True:
        - löscht nur managed Modelle in dieser App in sicherer Reihenfolge
        - löscht KEINE Patienten
    """
    random.seed(RANDOM_SEED)
    stats: dict[str, int] = {}

    with transaction.atomic():
        if flush:
            _flush_appointments()

        appointment_types = _seed_appointment_types()
        stats["appointments_types"] = len(appointment_types)

        practice_hours = _seed_practice_hours()
        stats["appointments_practice_hours"] = len(practice_hours)

        doctors = list(User.objects.filter(role__name="doctor"))
        resources = _seed_resources()
        stats["appointments_resources"] = len(resources)

        doctor_hours = _seed_doctor_hours(doctors)
        stats["appointments_doctor_hours"] = len(doctor_hours)

        absences = _seed_doctor_absences(doctors)
        stats["appointments_doctor_absences"] = len(absences)

        breaks = _seed_doctor_breaks(doctors)
        stats["appointments_doctor_breaks"] = len(breaks)

        appointments = _seed_appointments(appointment_types, doctors, resources)
        stats["appointments_appointments"] = len(appointments)

        op_types = _seed_operation_types()
        stats["appointments_operation_types"] = len(op_types)

        operations = _seed_operations(op_types, doctors, resources)
        stats["appointments_operations"] = len(operations)

        flows = _seed_patient_flows(appointments, operations)
        stats["appointments_patient_flows"] = len(flows)

    return stats


def _flush_appointments():
    # Reihenfolge beachten: abhängige Modelle zuerst löschen
    PatientFlow.objects.all().delete()
    Operation.objects.all().delete()
    Appointment.objects.all().delete()
    DoctorBreak.objects.all().delete()
    DoctorAbsence.objects.all().delete()
    DoctorHours.objects.all().delete()
    PracticeHours.objects.all().delete()
    Resource.objects.all().delete()
    OperationType.objects.all().delete()
    AppointmentType.objects.all().delete()


def _seed_appointment_types() -> list[AppointmentType]:
    definitions = [
        ("Erstgespräch", "#1A73E8", 30),
        ("Kontrolle", "#34A853", 15),
        ("Blutabnahme", "#FBBC05", 10),
        ("Ultraschall", "#8A2BE2", 25),
        ("OP-Vorgespräch", "#FF8C00", 40),
        ("Nachsorge", "#20B2AA", 20),
    ]

    types: list[AppointmentType] = []
    for name, color, duration in definitions:
        obj, _ = AppointmentType.objects.get_or_create(
            name=name,
            defaults={
                "color": color,
                "duration_minutes": duration,
                "active": True,
            },
        )
        types.append(obj)
    return types


def _seed_practice_hours() -> list[PracticeHours]:
    # Mo–Fr 08:00–17:00, Sa 09:00–12:00
    PracticeHours.objects.all().delete()
    result: list[PracticeHours] = []

    for weekday in range(0, 5):  # Mo–Fr
        ph = PracticeHours.objects.create(
            weekday=weekday,
            start_time=time(8, 0),
            end_time=time(17, 0),
            active=True,
        )
        result.append(ph)

    # Samstag
    ph = PracticeHours.objects.create(
        weekday=5,
        start_time=time(9, 0),
        end_time=time(12, 0),
        active=True,
    )
    result.append(ph)

    return result


def _seed_doctor_hours(doctors: list[User]) -> list[DoctorHours]:
    result: list[DoctorHours] = []
    if not doctors:
        return result

    for doctor in doctors:
        for weekday in [0, 1, 2, 3, 4]:  # Mo–Fr
            if random.random() < 0.6:  # nicht jeden Tag
                dh = DoctorHours.objects.create(
                    doctor=doctor,
                    weekday=weekday,
                    start_time=time(9, 0),
                    end_time=time(15, 0),
                    active=True,
                )
                result.append(dh)
    return result


def _seed_doctor_absences(doctors: list[User]) -> list[DoctorAbsence]:
    result: list[DoctorAbsence] = []
    if not doctors:
        return result

    today = date.today()
    for doctor in doctors:
        if random.random() < 0.4:
            start = today + timedelta(days=random.randint(1, 14))
            end = start + timedelta(days=random.randint(1, 3))
            absence = DoctorAbsence.objects.create(
                doctor=doctor,
                start_date=start,
                end_date=end,
                reason="Urlaub",
                active=True,
            )
            result.append(absence)
    return result


def _seed_doctor_breaks(doctors: list[User]) -> list[DoctorBreak]:
    result: list[DoctorBreak] = []
    if not doctors:
        return result

    today = date.today()
    for doctor in doctors:
        for i in range(2):  # zwei Pausen an zwei Tagen
            day = today + timedelta(days=random.randint(0, 6))
            br = DoctorBreak.objects.create(
                doctor=doctor,
                date=day,
                start_time=time(12, 0),
                end_time=time(12, 30),
                reason="Mittagspause",
                active=True,
            )
            result.append(br)
    return result


def _seed_resources() -> list[Resource]:
    definitions = [
        ("OP-1", "room", "#8A2BE2"),
        ("OP-2", "room", "#6A5ACD"),
        ("Behandlungsraum 1", "room", "#1A73E8"),
        ("Behandlungsraum 2", "room", "#34A853"),
        ("Ultraschallgerät", "device", "#FF8C00"),
        ("EKG-Gerät", "device", "#FBBC05"),
    ]

    resources: list[Resource] = []
    for name, rtype, color in definitions:
        obj, _ = Resource.objects.get_or_create(
            name=name,
            defaults={"type": rtype, "color": color, "active": True},
        )
        resources.append(obj)
    return resources


def _seed_appointments(
    appointment_types: list[AppointmentType],
    doctors: list[User],
    resources: list[Resource],
) -> list[Appointment]:
    result: list[Appointment] = []
    if not doctors or not appointment_types:
        return result

    patients = list(Patient.objects.all())
    if not patients:
        return result

    now = datetime.now()

    status_choices = [
        Appointment.STATUS_SCHEDULED,
        Appointment.STATUS_CONFIRMED,
        Appointment.STATUS_CANCELLED,
        Appointment.STATUS_COMPLETED,
    ]

    for i in range(50):
        patient = random.choice(patients)
        doctor = random.choice(doctors)
        apptype = random.choice(appointment_types)

        start_offset_days = random.randint(-7, 7)
        start_offset_minutes = random.randint(0, 60 * 8)
        start = (now + timedelta(days=start_offset_days)).replace(hour=8, minute=0, second=0, microsecond=0)
        start = start + timedelta(minutes=start_offset_minutes)

        duration = apptype.duration_minutes or 20
        end = start + timedelta(minutes=duration)

        status = random.choices(
            status_choices,
            weights=[0.6, 0.2, 0.1, 0.1],
            k=1,
        )[0]

        appt = Appointment.objects.create(
            patient_id=patient.id,
            type=apptype,
            doctor=doctor,
            start_time=start,
            end_time=end,
            status=status,
            notes=f"Seed-Termin {i + 1}",
        )

        # 0–2 Ressourcen zuweisen
        active_resources = [r for r in resources if r.active]
        for res in random.sample(active_resources, k=random.randint(0, min(2, len(active_resources)))):
            appt.resources.add(res)

        result.append(appt)

    return result


def _seed_operation_types() -> list[OperationType]:
    definitions = [
        ("Appendektomie", 30, 60, 30, "#8A2BE2"),
        ("Arthroskopie", 20, 45, 20, "#1A73E8"),
        ("Hernien-OP", 25, 50, 25, "#34A853"),
        ("Katarakt-OP", 15, 40, 20, "#FF8C00"),
    ]

    result: list[OperationType] = []
    for name, prep, op, post, color in definitions:
        obj, _ = OperationType.objects.get_or_create(
            name=name,
            defaults={
                "prep_duration": prep,
                "op_duration": op,
                "post_duration": post,
                "color": color,
                "active": True,
            },
        )
        result.append(obj)
    return result


def _seed_operations(
    op_types: list[OperationType],
    doctors: list[User],
    resources: list[Resource],
) -> list[Operation]:
    result: list[Operation] = []
    if not op_types or not doctors:
        return result

    patients = list(Patient.objects.all())
    if not patients:
        return result

    op_rooms = [r for r in resources if r.type == "room"]
    op_devices = [r for r in resources if r.type == "device"]
    if not op_rooms:
        return result

    now = datetime.now()

    for i in range(5):
        patient = random.choice(patients)
        primary = random.choice(doctors)
        assistants = [d for d in doctors if d != primary]
        assistant = random.choice(assistants) if assistants and random.random() < 0.7 else None
        anesthesist = random.choice(doctors) if random.random() < 0.7 else None

        room = random.choice(op_rooms)
        op_type = random.choice(op_types)

        start_offset_days = random.randint(-3, 3)
        start = now + timedelta(days=start_offset_days)
        start = start.replace(hour=10, minute=0, second=0, microsecond=0)

        duration = op_type.prep_duration + op_type.op_duration + op_type.post_duration
        end = start + timedelta(minutes=duration or 90)

        status = random.choice(
            [
                Operation.STATUS_PLANNED,
                Operation.STATUS_CONFIRMED,
                Operation.STATUS_RUNNING,
                Operation.STATUS_DONE,
            ]
        )

        op = Operation.objects.create(
            patient_id=patient.id,
            primary_surgeon=primary,
            assistant=assistant,
            anesthesist=anesthesist,
            op_room=room,
            op_type=op_type,
            start_time=start,
            end_time=end,
            status=status,
            notes=f"Seed-OP {i + 1}",
        )

        # 0–2 Geräte zuweisen
        if op_devices:
            for dev in random.sample(op_devices, k=random.randint(0, min(2, len(op_devices)))):
                op.op_devices.add(dev)

        result.append(op)

    return result


def _seed_patient_flows(
    appointments: list[Appointment],
    operations: list[Operation],
) -> list[PatientFlow]:
    result: list[PatientFlow] = []

    now = datetime.now()

    # Für Termine
    for appt in appointments:
        status = random.choice(
            [
                PatientFlow.STATUS_REGISTERED,
                PatientFlow.STATUS_WAITING,
                PatientFlow.STATUS_PREPARING,
                PatientFlow.STATUS_IN_TREATMENT,
                PatientFlow.STATUS_POST_TREATMENT,
                PatientFlow.STATUS_DONE,
            ]
        )
        arrival = appt.start_time - timedelta(minutes=random.randint(5, 20))

        pf = PatientFlow.objects.create(
            appointment=appt,
            operation=None,
            status=status,
            arrival_time=arrival if random.random() < 0.9 else None,
            status_changed_at=now - timedelta(minutes=random.randint(0, 60)),
            notes="Seed-PatientFlow (Termin)",
        )
        result.append(pf)

    # Für Operationen
    for op in operations:
        status = random.choice(
            [
                PatientFlow.STATUS_PREPARING,
                PatientFlow.STATUS_IN_TREATMENT,
                PatientFlow.STATUS_POST_TREATMENT,
                PatientFlow.STATUS_DONE,
            ]
        )
        arrival = op.start_time - timedelta(minutes=random.randint(15, 60))

        pf = PatientFlow.objects.create(
            appointment=None,
            operation=op,
            status=status,
            arrival_time=arrival,
            status_changed_at=now - timedelta(minutes=random.randint(0, 120)),
            notes="Seed-PatientFlow (OP)",
        )
        result.append(pf)

    return result