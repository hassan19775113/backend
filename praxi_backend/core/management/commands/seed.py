"""
PraxiApp Seed Command – erzeugt reproduzierbare Testdaten.

Verwendung:
    python manage.py seed           # Seed für alle Apps
    python manage.py seed --flush   # Testdaten in managed-Tabellen löschen und neu aufbauen

WICHTIG:
- Die Patienten-Tabelle (medical.Patient, managed=False) wird NIE gelöscht.
- Patienten werden nur erzeugt, wenn die Tabelle leer ist.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from core.seeders import seed_core
from appointments.seeders import seed_appointments
from medical.seeders import seed_medical


class Command(BaseCommand):
    help = "Seed database with realistic test data for PraxiApp"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing test data in managed tables before seeding (Patienten bleiben unangetastet).",
        )

    def handle(self, *args, **options):
        flush = options.get("flush", False)

        self.stdout.write("=" * 80)
        self.stdout.write("  PraxiApp Seed – Testdaten generieren")
        self.stdout.write("=" * 80)

        try:
            with transaction.atomic():
                stats = {}

                # 1. Core (Rollen, Benutzer, AuditLog)
                self.stdout.write("\n[1/3] Seeding Core (Roles, Users, AuditLog)...")
                core_stats = seed_core(flush=flush)
                stats.update(core_stats)
                self._print_stats("Core", core_stats)

                # 2. Medical (Patienten) – unmanaged, wird nie gelöscht
                self.stdout.write("\n[2/3] Seeding Medical (Patients)...")
                medical_stats = seed_medical()
                stats.update(medical_stats)
                self._print_stats("Medical", medical_stats)

                # 3. Appointments (Termine, Ressourcen, OPs, PatientFlow)
                self.stdout.write("\n[3/3] Seeding Appointments (Appointments, Resources, Operations, Flows)...")
                appointments_stats = seed_appointments(flush=flush)
                stats.update(appointments_stats)
                self._print_stats("Appointments", appointments_stats)

                self.stdout.write("\n" + "=" * 80)
                self.stdout.write("  ✓ Seeding erfolgreich abgeschlossen!")
                self.stdout.write("=" * 80)
                self._print_summary(stats)

        except Exception as e:
            self.stdout.write(f"\n✗ Fehler beim Seeding: {e}")
            raise

    def _print_stats(self, section, stats):
        for key, value in stats.items():
            self.stdout.write(f"  ✓ {key}: {value}")

    def _print_summary(self, stats):
        self.stdout.write("\nErstellte Datensätze (gesamt):")
        for key, value in sorted(stats.items()):
            self.stdout.write(f"  • {key}: {value}")