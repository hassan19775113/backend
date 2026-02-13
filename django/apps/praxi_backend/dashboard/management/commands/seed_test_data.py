from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from praxi_backend.appointments.models import Appointment, Resource
from praxi_backend.core.models import Role, User as Doctor
from praxi_backend.patients.models import Patient


class Command(BaseCommand):
    help = "Create minimal CI seed data (doctor, patient, resource, appointment)."

    def handle(self, *args, **options):
        doctor_role, _ = Role.objects.using("default").get_or_create(
            name="doctor",
            defaults={"label": "Arzt"},
        )

        doctor, created_doctor = Doctor.objects.using("default").get_or_create(
            username="ci_seed_doctor",
            defaults={
                "email": "ci_seed_doctor@local.test",
                "first_name": "CI",
                "last_name": "Doctor",
                "is_active": True,
                "is_staff": True,
                "role": doctor_role,
            },
        )
        if created_doctor:
            doctor.set_password("test1234")
        if doctor.role_id != doctor_role.id:
            doctor.role = doctor_role
        doctor.save(using="default")

        next_patient_id = (
            (Patient.objects.using("default").order_by("-id").values_list("id", flat=True).first() or 0)
            + 1
        )
        patient, _ = Patient.objects.using("default").get_or_create(
            id=next_patient_id,
            defaults={
                "first_name": "CI",
                "last_name": "Patient",
            },
        )

        resource, _ = Resource.objects.using("default").get_or_create(
            name="CI Seed Room",
            type=Resource.TYPE_ROOM,
            defaults={
                "active": True,
                "color": "#6A5ACD",
            },
        )

        start_time = timezone.now() + timedelta(hours=1)
        end_time = start_time + timedelta(minutes=30)

        appointment = Appointment.objects.using("default").create(
            patient_id=patient.id,
            doctor=doctor,
            start_time=start_time,
            end_time=end_time,
            notes="CI seed appointment",
        )
        appointment.resources.add(resource)

        self.stdout.write(
            self.style.SUCCESS(
                "seed_test_data complete: "
                f"doctor={doctor.username}, patient_id={patient.id}, resource_id={resource.id}, appointment_id={appointment.id}"
            )
        )
