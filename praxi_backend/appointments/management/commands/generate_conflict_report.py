"""
Management Command: generate_conflict_report

Generates a comprehensive scheduling conflict report.

Usage:
    python manage.py generate_conflict_report
    python manage.py generate_conflict_report --seed 42
    python manage.py generate_conflict_report --json
    python manage.py generate_conflict_report --output report.json
    python manage.py generate_conflict_report --no-examples

==============================================================================
"""

import sys
from datetime import datetime

from django.core.management.base import BaseCommand

from praxi_backend.appointments.services.scheduling_conflict_report import (
    format_text_report,
    generate_conflict_report,
    print_conflict_report,
)


class Command(BaseCommand):
    help = "Generate a comprehensive scheduling conflict report."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Random seed for reproducible test data (default: None = random)",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output report as JSON instead of text",
        )
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default=None,
            help="Write report to file instead of stdout",
        )
        parser.add_argument(
            "--no-examples",
            action="store_true",
            help="Skip generating conflict examples (faster)",
        )
        parser.add_argument(
            "--summary-only",
            action="store_true",
            help="Output only the summary section",
        )

    def handle(self, *args, **options):
        seed = options.get("seed")
        output_json = options.get("json")
        output_file = options.get("output")
        no_examples = options.get("no_examples")
        summary_only = options.get("summary_only")

        self.stdout.write(
            self.style.NOTICE("\n" + "=" * 80)
        )
        self.stdout.write(
            self.style.NOTICE("SCHEDULING CONFLICT REPORT GENERATOR")
        )
        self.stdout.write(
            self.style.NOTICE("=" * 80 + "\n")
        )

        if seed:
            self.stdout.write(f"Using seed: {seed}")
        else:
            self.stdout.write("Using random seed (use --seed for reproducibility)")

        self.stdout.write("\nGenerating conflict report...")
        self.stdout.write("This may take a moment as test data is created.\n")

        try:
            # Generate the report
            report = generate_conflict_report(seed=seed)

            # Handle output format
            if output_json:
                output = report.to_json()
            elif summary_only:
                output = self._format_summary_only(report)
            else:
                output = format_text_report(report)

            # Handle output destination
            if output_file:
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(output)
                self.stdout.write(
                    self.style.SUCCESS(f"\nReport written to: {output_file}")
                )
                self.stdout.write(f"Total conflicts found: {report.summary.total_conflicts}")
                self.stdout.write(f"Critical conflicts: {report.summary.critical_conflicts}")
            else:
                # Print to stdout
                self.stdout.write("\n")
                self.stdout.write(output)

            # Print final stats
            self.stdout.write("\n" + "=" * 80)
            self.stdout.write(
                self.style.SUCCESS(f"✓ Report generated successfully")
            )
            self.stdout.write(f"  Total conflicts: {report.summary.total_conflicts}")
            self.stdout.write(f"  High priority: {report.summary.by_priority.get('high', 0)}")
            self.stdout.write(f"  Medium priority: {report.summary.by_priority.get('medium', 0)}")
            self.stdout.write(f"  Low priority: {report.summary.by_priority.get('low', 0)}")
            self.stdout.write("=" * 80 + "\n")

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f"Error generating report: {e}")
            )
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def _format_summary_only(self, report):
        """Format only the summary section."""
        lines = []
        lines.append("=" * 80)
        lines.append("SCHEDULING CONFLICT REPORT - SUMMARY")
        lines.append(f"Generated: {report.timestamp}")
        lines.append(f"Report ID: {report.report_id}")
        lines.append("=" * 80)
        lines.append("")

        summary = report.summary
        lines.append(f"Total Conflicts: {summary.total_conflicts}")
        lines.append(f"Critical Conflicts (HIGH priority): {summary.critical_conflicts}")
        lines.append("")

        lines.append("By Category:")
        for cat, count in sorted(summary.by_category.items(), key=lambda x: -x[1]):
            lines.append(f"  - {cat}: {count}")
        lines.append("")

        lines.append("By Priority:")
        for pri, count in sorted(summary.by_priority.items()):
            lines.append(f"  - {pri}: {count}")
        lines.append("")

        lines.append("Recommendations:")
        for i, rec in enumerate(summary.recommendations, 1):
            lines.append(f"  {i}. {rec}")
        lines.append("")

        return "\n".join(lines)
