"""
Management command to generate scheduling dashboard.

Usage:
    python manage.py generate_dashboard
    python manage.py generate_dashboard --seed 42
    python manage.py generate_dashboard --date 2025-12-29
    python manage.py generate_dashboard --output dashboard.txt
    python manage.py generate_dashboard --real-data
"""

from datetime import datetime

from django.core.management.base import BaseCommand

from praxi_backend.appointments.services.scheduling_dashboard import (
    generate_dashboard,
)


class Command(BaseCommand):
    help = "Generate a text-based scheduling dashboard"

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Random seed for reproducible demo data",
        )
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Target date (YYYY-MM-DD format)",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Output file path (prints to stdout if not specified)",
        )
        parser.add_argument(
            "--real-data",
            action="store_true",
            help="Use real database data instead of demo data",
        )

    def handle(self, *args, **options):
        seed = options.get("seed")
        date_str = options.get("date")
        output_file = options.get("output")
        use_demo = not options.get("real_data", False)

        target_date = None
        if date_str:
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid date format: {date_str}"))
                return

        self.stdout.write(f"Generating scheduling dashboard...")
        if seed:
            self.stdout.write(f"Seed: {seed}")
        if target_date:
            self.stdout.write(f"Date: {target_date}")
        self.stdout.write("")

        content = generate_dashboard(
            target_date=target_date,
            seed=seed,
            use_demo=use_demo,
        )

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)
            self.stdout.write(self.style.SUCCESS(f"✓ Dashboard written to: {output_file}"))
        else:
            self.stdout.write(content)
