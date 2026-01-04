"""
Django Management Command: simulate_scheduling

Run scheduling conflict simulations from the command line.

Usage:
    python manage.py simulate_scheduling
    python manage.py simulate_scheduling --seed 12345
    python manage.py simulate_scheduling --scenario doctor_conflict
    python manage.py simulate_scheduling --json

Examples:
    # Run all simulations with default seed
    python manage.py simulate_scheduling

    # Run with specific seed for reproducibility
    python manage.py simulate_scheduling --seed 42

    # Run only specific scenarios
    python manage.py simulate_scheduling --scenario doctor_conflict --scenario room_conflict

    # Output as JSON (for CI/CD integration)
    python manage.py simulate_scheduling --json

    # Verbose mode with detailed output
    python manage.py simulate_scheduling -v 2
"""

import json
import sys
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from praxi_backend.appointments.services.scheduling_simulation import (
    DEFAULT_SEED,
    SimulationContext,
    SimulationSummary,
    print_simulation_report,
    run_all_simulations,
    simulate_appointment_overlap,
    simulate_device_conflict,
    simulate_doctor_absence,
    simulate_doctor_break,
    simulate_doctor_conflict,
    simulate_edge_cases,
    simulate_full_day_load,
    simulate_operation_overlap,
    simulate_patient_double_booking,
    simulate_randomized_day,
    simulate_room_conflict,
    simulate_team_conflict,
    simulate_working_hours_violation,
)


SCENARIO_FUNCTIONS = {
    "doctor_conflict": simulate_doctor_conflict,
    "room_conflict": simulate_room_conflict,
    "device_conflict": simulate_device_conflict,
    "appointment_overlap": simulate_appointment_overlap,
    "operation_overlap": simulate_operation_overlap,
    "working_hours_violation": simulate_working_hours_violation,
    "doctor_absence": simulate_doctor_absence,
    "doctor_break": simulate_doctor_break,
    "patient_double_booking": simulate_patient_double_booking,
    "team_conflict": simulate_team_conflict,
    "full_day_load": simulate_full_day_load,
    "randomized_day": simulate_randomized_day,
}


class Command(BaseCommand):
    """Run scheduling conflict simulations."""

    help = "Run scheduling conflict simulations to test the scheduling engine"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--seed",
            type=int,
            default=DEFAULT_SEED,
            help=f"Random seed for deterministic results (default: {DEFAULT_SEED})",
        )
        parser.add_argument(
            "--scenario",
            action="append",
            dest="scenarios",
            choices=list(SCENARIO_FUNCTIONS.keys()) + ["edge_cases", "all"],
            help="Specific scenario(s) to run. Can be repeated. (default: all)",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="output_json",
            help="Output results as JSON (for CI/CD)",
        )
        parser.add_argument(
            "--fail-fast",
            action="store_true",
            help="Stop on first failure",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        seed = options["seed"]
        scenarios = options.get("scenarios") or ["all"]
        output_json = options["output_json"]
        fail_fast = options["fail_fast"]
        verbosity = options["verbosity"]

        if verbosity >= 2:
            self.stdout.write(f"Using seed: {seed}")
            self.stdout.write(f"Scenarios: {scenarios}")

        try:
            # Run in atomic transaction (rollback all test data)
            with transaction.atomic(using="default"):
                if "all" in scenarios:
                    summary = run_all_simulations(seed=seed)
                else:
                    summary = self._run_selected_scenarios(
                        scenarios, seed, fail_fast
                    )

                # Output results
                if output_json:
                    self.stdout.write(json.dumps(summary.to_dict(), indent=2))
                else:
                    self._print_report(summary, verbosity)

                # Rollback (don't persist test data)
                transaction.set_rollback(True, using="default")

            # Exit code based on results
            if summary.failed > 0:
                raise CommandError(
                    f"{summary.failed} simulation(s) failed. "
                    "Run with -v 2 for details."
                )

            return f"All {summary.passed} simulations passed."

        except Exception as e:
            if output_json:
                self.stdout.write(json.dumps({"error": str(e)}))
            raise

    def _run_selected_scenarios(
        self,
        scenarios: list[str],
        seed: int,
        fail_fast: bool,
    ) -> SimulationSummary:
        """Run only selected scenarios."""
        summary = SimulationSummary()
        ctx = SimulationContext(seed=seed)
        ctx.setup()

        for scenario in scenarios:
            if scenario == "edge_cases":
                for result in simulate_edge_cases(ctx):
                    summary.add(result)
                    if fail_fast and not result.success:
                        return summary
            elif scenario == "randomized_day":
                result = simulate_randomized_day(ctx, seed=seed)
                summary.add(result)
                if fail_fast and not result.success:
                    return summary
            elif scenario in SCENARIO_FUNCTIONS:
                func = SCENARIO_FUNCTIONS[scenario]
                result = func(ctx)
                summary.add(result)
                if fail_fast and not result.success:
                    return summary

        return summary

    def _print_report(self, summary: SimulationSummary, verbosity: int) -> None:
        """Print human-readable report."""
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("=" * 70))
        self.stdout.write(self.style.HTTP_INFO("SCHEDULING SIMULATION REPORT"))
        self.stdout.write(self.style.HTTP_INFO("=" * 70))

        # Summary line
        total_style = self.style.SUCCESS if summary.failed == 0 else self.style.ERROR
        self.stdout.write(
            total_style(
                f"Total: {summary.total} | "
                f"Passed: {summary.passed} | "
                f"Failed: {summary.failed}"
            )
        )

        if verbosity >= 1:
            self.stdout.write("-" * 70)
            for result in summary.results:
                if result.success:
                    status = self.style.SUCCESS("✓ PASS")
                else:
                    status = self.style.ERROR("✗ FAIL")

                self.stdout.write(f"{status}  {result.scenario}")

                if verbosity >= 2:
                    if result.message:
                        self.stdout.write(f"        {result.message}")
                    if result.conflicts:
                        self.stdout.write(
                            f"        Conflicts: {len(result.conflicts)}"
                        )
                    if result.duration_ms > 0:
                        self.stdout.write(
                            f"        Duration: {result.duration_ms:.2f}ms"
                        )

        self.stdout.write("=" * 70)
