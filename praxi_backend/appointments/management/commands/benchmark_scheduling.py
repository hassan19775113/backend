"""
Django Management Command: benchmark_scheduling

Run comprehensive scheduling engine benchmarks from the command line.

Usage:
    python manage.py benchmark_scheduling
    python manage.py benchmark_scheduling --seed 12345
    python manage.py benchmark_scheduling --quick
    python manage.py benchmark_scheduling --json

Examples:
    # Run full benchmark suite
    python manage.py benchmark_scheduling

    # Quick benchmark (reduced iterations)
    python manage.py benchmark_scheduling --quick

    # Output as JSON (for CI/CD or data collection)
    python manage.py benchmark_scheduling --json

    # Specific seed for reproducibility
    python manage.py benchmark_scheduling --seed 42

    # Run specific benchmark only
    python manage.py benchmark_scheduling --benchmark single_day_load
"""

import json
import sys
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from praxi_backend.appointments.services.scheduling_benchmark import (
    DEFAULT_SEED,
    BenchmarkContext,
    BenchmarkReport,
    benchmark_conflict_detection,
    benchmark_full_engine,
    benchmark_no_conflict,
    benchmark_randomized,
    benchmark_room_conflicts,
    benchmark_single_day_load,
    benchmark_working_hours_validation,
    generate_report,
    print_benchmark_report,
)


BENCHMARK_FUNCTIONS = {
    "single_day_load": lambda ctx, q: benchmark_single_day_load(
        ctx, n_appointments=20 if q else 50, n_operations=10 if q else 20
    ),
    "conflict_detection": lambda ctx, q: benchmark_conflict_detection(
        ctx, n_checks=100 if q else 500
    ),
    "no_conflict": lambda ctx, q: benchmark_no_conflict(
        ctx, n_checks=100 if q else 500
    ),
    "working_hours": lambda ctx, q: benchmark_working_hours_validation(
        ctx, n_checks=50 if q else 200
    ),
    "room_conflicts": lambda ctx, q: benchmark_room_conflicts(
        ctx, n_checks=50 if q else 200
    ),
    "randomized": lambda ctx, q: benchmark_randomized(
        ctx, seed=ctx.seed, n=30 if q else 100
    ),
}


class Command(BaseCommand):
    """Run scheduling engine benchmarks."""

    help = "Run comprehensive scheduling engine performance benchmarks"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--seed",
            type=int,
            default=DEFAULT_SEED,
            help=f"Random seed for deterministic results (default: {DEFAULT_SEED})",
        )
        parser.add_argument(
            "--quick",
            action="store_true",
            help="Run quick benchmarks with reduced iterations",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="output_json",
            help="Output results as JSON",
        )
        parser.add_argument(
            "--benchmark",
            action="append",
            dest="benchmarks",
            choices=list(BENCHMARK_FUNCTIONS.keys()) + ["all"],
            help="Specific benchmark(s) to run. Can be repeated. (default: all)",
        )
        parser.add_argument(
            "--no-rollback",
            action="store_true",
            help="Don't rollback test data (for debugging)",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        seed = options["seed"]
        quick = options["quick"]
        output_json = options["output_json"]
        benchmarks = options.get("benchmarks") or ["all"]
        no_rollback = options["no_rollback"]
        verbosity = options["verbosity"]

        if verbosity >= 2 and not output_json:
            self.stdout.write(f"Using seed: {seed}")
            self.stdout.write(f"Quick mode: {quick}")
            self.stdout.write(f"Benchmarks: {benchmarks}")

        try:
            if no_rollback:
                report = self._run_benchmarks(seed, quick, benchmarks)
            else:
                # Run in atomic transaction (rollback all test data)
                with transaction.atomic(using="default"):
                    report = self._run_benchmarks(seed, quick, benchmarks)
                    transaction.set_rollback(True, using="default")

            # Output results
            if output_json:
                self.stdout.write(json.dumps(report.to_dict(), indent=2))
            else:
                self._print_report(report, verbosity)

            return f"Benchmark completed in {report.total_duration_sec:.2f}s"

        except Exception as e:
            if output_json:
                self.stdout.write(json.dumps({"error": str(e)}))
            raise CommandError(f"Benchmark failed: {e}")

    def _run_benchmarks(
        self,
        seed: int,
        quick: bool,
        benchmarks: list[str],
    ) -> BenchmarkReport:
        """Run selected benchmarks."""
        import time
        
        if "all" in benchmarks:
            return benchmark_full_engine(seed=seed)
        
        ctx = BenchmarkContext(seed=seed)
        ctx.setup()
        
        results = []
        start = time.perf_counter()
        
        for name in benchmarks:
            if name in BENCHMARK_FUNCTIONS:
                func = BENCHMARK_FUNCTIONS[name]
                result = func(ctx, quick)
                results.append(result)
        
        end = time.perf_counter()
        
        report = generate_report(results)
        report.total_duration_sec = end - start
        
        return report

    def _print_report(self, report: BenchmarkReport, verbosity: int) -> None:
        """Print human-readable report."""
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("=" * 80))
        self.stdout.write(self.style.HTTP_INFO("SCHEDULING ENGINE BENCHMARK REPORT"))
        self.stdout.write(self.style.HTTP_INFO("=" * 80))
        self.stdout.write(f"Timestamp: {report.timestamp}")
        self.stdout.write(f"Total Duration: {report.total_duration_sec:.2f}s")
        self.stdout.write("")

        self.stdout.write("-" * 80)
        self.stdout.write("INDIVIDUAL BENCHMARKS")
        self.stdout.write("-" * 80)

        for r in report.results:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(f"📊 {r.name}"))
            self.stdout.write(f"   {r.description}")
            self.stdout.write(
                f"   Operations: {r.timing.count} | "
                f"Throughput: {r.throughput_ops_sec:.1f} ops/sec"
            )
            self.stdout.write(
                f"   Avg: {r.timing.avg_ms:.3f}ms | "
                f"Min: {r.timing.min_ms:.3f}ms | "
                f"Max: {r.timing.max_ms:.3f}ms"
            )
            
            if verbosity >= 2:
                self.stdout.write(
                    f"   P95: {r.timing.p95_ms:.3f}ms | "
                    f"P99: {r.timing.p99_ms:.3f}ms"
                )
                self.stdout.write(
                    f"   Queries: {r.queries.total_queries} total "
                    f"({r.queries.queries_per_op:.1f}/op)"
                )
                if r.conflicts_detected:
                    self.stdout.write(f"   Conflicts: {r.conflicts_detected}")

        self.stdout.write("")
        self.stdout.write("-" * 80)
        self.stdout.write("SUMMARY")
        self.stdout.write("-" * 80)
        for key, value in report.summary.items():
            self.stdout.write(f"   {key}: {value}")

        if report.bottlenecks:
            self.stdout.write("")
            self.stdout.write("-" * 80)
            self.stdout.write(self.style.WARNING("⚠️  BOTTLENECKS IDENTIFIED"))
            self.stdout.write("-" * 80)
            for b in report.bottlenecks:
                self.stdout.write(f"   • {b}")

        self.stdout.write("")
        self.stdout.write("-" * 80)
        self.stdout.write(self.style.SUCCESS("💡 RECOMMENDATIONS"))
        self.stdout.write("-" * 80)
        for rec in report.recommendations:
            self.stdout.write(f"   • {rec}")

        self.stdout.write("=" * 80)
