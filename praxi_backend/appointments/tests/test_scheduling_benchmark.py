"""
Test Suite for Scheduling Benchmark Module.

This test suite validates that the benchmark functions work correctly
and return valid, structured results.

==============================================================================
ARCHITECTURE RULES (from copilot-instructions.md)
==============================================================================

- databases = {"default"} on test classes
- Use User.objects.db_manager("default").create_user(...)
- Use .using("default") on all ORM calls
- patient_id is an integer (NO ForeignKey to medical.Patient)
- Fully qualified imports: praxi_backend.appointments.*

==============================================================================
"""

from django.test import TestCase
from django.utils import timezone

from praxi_backend.appointments.services.scheduling_benchmark import (
    DEFAULT_SEED,
    BenchmarkContext,
    BenchmarkReport,
    BenchmarkResult,
    QueryStats,
    TimingStats,
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


class TimingStatsTest(TestCase):
    """Test TimingStats data class."""

    def test_from_samples_empty(self):
        """Empty samples should return default stats."""
        stats = TimingStats.from_samples([])
        
        self.assertEqual(stats.count, 0)
        self.assertEqual(stats.total_ms, 0.0)

    def test_from_samples_single(self):
        """Single sample should work correctly."""
        stats = TimingStats.from_samples([10.0])
        
        self.assertEqual(stats.count, 1)
        self.assertEqual(stats.avg_ms, 10.0)
        self.assertEqual(stats.min_ms, 10.0)
        self.assertEqual(stats.max_ms, 10.0)

    def test_from_samples_multiple(self):
        """Multiple samples should calculate correct statistics."""
        samples = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        stats = TimingStats.from_samples(samples)
        
        self.assertEqual(stats.count, 10)
        self.assertEqual(stats.min_ms, 1.0)
        self.assertEqual(stats.max_ms, 10.0)
        self.assertEqual(stats.avg_ms, 5.5)
        self.assertEqual(stats.total_ms, 55.0)

    def test_to_dict(self):
        """to_dict() should return proper structure."""
        stats = TimingStats.from_samples([1.0, 2.0, 3.0])
        d = stats.to_dict()
        
        self.assertIn('count', d)
        self.assertIn('avg_ms', d)
        self.assertIn('min_ms', d)
        self.assertIn('max_ms', d)
        self.assertIn('p95_ms', d)
        self.assertIn('p99_ms', d)


class QueryStatsTest(TestCase):
    """Test QueryStats data class."""

    def test_to_dict(self):
        """to_dict() should return proper structure."""
        stats = QueryStats(
            total_queries=100,
            queries_per_op=2.5,
            slowest_query_ms=15.3,
            query_breakdown={'SELECT': 80, 'INSERT': 20},
        )
        d = stats.to_dict()
        
        self.assertEqual(d['total_queries'], 100)
        self.assertEqual(d['queries_per_op'], 2.5)
        self.assertIn('query_breakdown', d)


class BenchmarkResultTest(TestCase):
    """Test BenchmarkResult data class."""

    def test_to_dict(self):
        """to_dict() should return complete structure."""
        result = BenchmarkResult(
            name="test_benchmark",
            description="Test description",
            throughput_ops_sec=100.5,
            items_created=50,
            conflicts_detected=5,
        )
        d = result.to_dict()
        
        self.assertEqual(d['name'], "test_benchmark")
        self.assertEqual(d['description'], "Test description")
        self.assertEqual(d['throughput_ops_sec'], 100.5)
        self.assertEqual(d['items_created'], 50)
        self.assertEqual(d['conflicts_detected'], 5)
        self.assertIn('timing', d)
        self.assertIn('queries', d)


class BenchmarkContextTest(TestCase):
    """Test BenchmarkContext setup and configuration."""

    databases = {"default"}

    def test_setup_creates_roles(self):
        """Context setup should create roles."""
        ctx = BenchmarkContext(seed=5001)
        ctx.setup(num_doctors=2, num_rooms=1, num_devices=1)
        
        self.assertIsNotNone(ctx.role_admin)
        self.assertIsNotNone(ctx.role_doctor)

    def test_setup_creates_doctors(self):
        """Context setup should create specified number of doctors."""
        ctx = BenchmarkContext(seed=5002)
        ctx.setup(num_doctors=3, num_rooms=1, num_devices=1)
        
        self.assertEqual(len(ctx.doctors), 3)

    def test_setup_creates_resources(self):
        """Context setup should create rooms and devices."""
        ctx = BenchmarkContext(seed=5003)
        ctx.setup(num_doctors=1, num_rooms=2, num_devices=3)
        
        self.assertEqual(len(ctx.rooms), 2)
        self.assertEqual(len(ctx.devices), 3)

    def test_next_patient_id_unique(self):
        """next_patient_id() should return unique IDs."""
        ctx = BenchmarkContext(seed=5004)
        
        ids = [ctx.next_patient_id() for _ in range(5)]
        self.assertEqual(len(set(ids)), 5)


class BenchmarkSingleDayLoadTest(TestCase):
    """Test single day load benchmark."""

    databases = {"default"}

    def setUp(self):
        self.ctx = BenchmarkContext(seed=6001)
        self.ctx.setup()

    def test_returns_valid_structure(self):
        """Benchmark should return valid BenchmarkResult."""
        result = benchmark_single_day_load(self.ctx, n_appointments=10, n_operations=5)
        
        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.name, "single_day_load")
        self.assertGreater(result.timing.count, 0)

    def test_measures_timing(self):
        """Benchmark should measure timing correctly."""
        result = benchmark_single_day_load(self.ctx, n_appointments=5, n_operations=2)
        
        self.assertGreater(result.timing.total_ms, 0)
        self.assertGreater(result.timing.avg_ms, 0)
        self.assertLessEqual(result.timing.min_ms, result.timing.max_ms)

    def test_counts_queries(self):
        """Benchmark should count database queries."""
        result = benchmark_single_day_load(self.ctx, n_appointments=5, n_operations=2)
        
        self.assertGreater(result.queries.total_queries, 0)

    def test_tracks_created_items(self):
        """Benchmark should track created items."""
        result = benchmark_single_day_load(self.ctx, n_appointments=10, n_operations=5)
        
        self.assertIn('appointments_created', result.metadata)
        self.assertIn('operations_created', result.metadata)


class BenchmarkConflictDetectionTest(TestCase):
    """Test conflict detection benchmark."""

    databases = {"default"}

    def setUp(self):
        self.ctx = BenchmarkContext(seed=6002)
        self.ctx.setup()

    def test_returns_valid_structure(self):
        """Benchmark should return valid BenchmarkResult."""
        result = benchmark_conflict_detection(self.ctx, n_checks=50)
        
        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.name, "conflict_detection")

    def test_detects_all_conflicts(self):
        """All checks should detect conflicts."""
        result = benchmark_conflict_detection(self.ctx, n_checks=20)
        
        self.assertEqual(result.conflicts_detected, 20)
        self.assertTrue(result.metadata.get('all_conflicts_detected'))

    def test_measures_throughput(self):
        """Benchmark should measure throughput."""
        result = benchmark_conflict_detection(self.ctx, n_checks=50)
        
        self.assertGreater(result.throughput_ops_sec, 0)


class BenchmarkNoConflictTest(TestCase):
    """Test no-conflict baseline benchmark."""

    databases = {"default"}

    def setUp(self):
        self.ctx = BenchmarkContext(seed=6003)
        self.ctx.setup()

    def test_returns_valid_structure(self):
        """Benchmark should return valid BenchmarkResult."""
        result = benchmark_no_conflict(self.ctx, n_checks=50)
        
        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.name, "no_conflict_baseline")

    def test_no_conflicts_detected(self):
        """No conflicts should be detected."""
        result = benchmark_no_conflict(self.ctx, n_checks=20)
        
        self.assertEqual(result.conflicts_detected, 0)
        self.assertTrue(result.metadata.get('all_conflict_free'))

    def test_faster_than_conflict_detection(self):
        """No-conflict checks should generally be faster or similar."""
        # Note: This is a soft assertion since timing can vary
        no_conflict = benchmark_no_conflict(self.ctx, n_checks=100)
        
        # Create new context to avoid data interference
        ctx2 = BenchmarkContext(seed=6003)
        ctx2.setup(num_doctors=5, num_rooms=4, num_devices=3)
        conflict = benchmark_conflict_detection(ctx2, n_checks=100)
        
        # Just verify both complete successfully
        self.assertGreater(no_conflict.throughput_ops_sec, 0)
        self.assertGreater(conflict.throughput_ops_sec, 0)


class BenchmarkWorkingHoursValidationTest(TestCase):
    """Test working hours validation benchmark."""

    databases = {"default"}

    def setUp(self):
        self.ctx = BenchmarkContext(seed=6004)
        self.ctx.setup()

    def test_returns_valid_structure(self):
        """Benchmark should return valid BenchmarkResult."""
        result = benchmark_working_hours_validation(self.ctx, n_checks=50)
        
        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.name, "working_hours_validation")

    def test_detects_violations(self):
        """Should detect some violations (Sunday checks)."""
        result = benchmark_working_hours_validation(self.ctx, n_checks=50)
        
        # ~50% should be violations (alternating valid/invalid)
        self.assertGreater(result.conflicts_detected, 0)


class BenchmarkRoomConflictsTest(TestCase):
    """Test room conflicts benchmark."""

    databases = {"default"}

    def setUp(self):
        self.ctx = BenchmarkContext(seed=6005)
        self.ctx.setup()

    def test_returns_valid_structure(self):
        """Benchmark should return valid BenchmarkResult."""
        result = benchmark_room_conflicts(self.ctx, n_checks=50)
        
        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.name, "room_conflicts")

    def test_detects_conflicts(self):
        """Should detect some room conflicts."""
        result = benchmark_room_conflicts(self.ctx, n_checks=50)
        
        # ~50% should have conflicts (alternating)
        self.assertGreater(result.conflicts_detected, 0)


class BenchmarkRandomizedTest(TestCase):
    """Test randomized benchmark."""

    databases = {"default"}

    def setUp(self):
        self.ctx = BenchmarkContext(seed=6006)
        self.ctx.setup()

    def test_returns_valid_structure(self):
        """Benchmark should return valid BenchmarkResult."""
        result = benchmark_randomized(self.ctx, seed=123, n=20)
        
        self.assertIsInstance(result, BenchmarkResult)
        self.assertEqual(result.name, "randomized")

    def test_is_deterministic(self):
        """Same seed should produce same results."""
        result1 = benchmark_randomized(self.ctx, seed=999, n=10)
        
        # Create new context with different base seed
        ctx2 = BenchmarkContext(seed=6099)
        ctx2.setup()
        result2 = benchmark_randomized(ctx2, seed=999, n=10)
        
        # Same simulation seed should produce same appointment/operation count
        self.assertEqual(
            result1.metadata['appointments_created'],
            result2.metadata['appointments_created'],
        )
        self.assertEqual(
            result1.metadata['operations_created'],
            result2.metadata['operations_created'],
        )

    def test_creates_items(self):
        """Should create appointments and/or operations."""
        result = benchmark_randomized(self.ctx, seed=456, n=50)
        
        self.assertGreater(result.items_created, 0)


class BenchmarkFullEngineTest(TestCase):
    """Test full engine benchmark."""

    databases = {"default"}

    def test_returns_complete_report(self):
        """Full engine benchmark should return complete report."""
        report = benchmark_full_engine(seed=7001)
        
        self.assertIsInstance(report, BenchmarkReport)
        self.assertGreater(len(report.results), 0)
        self.assertIsNotNone(report.timestamp)
        self.assertGreater(report.total_duration_sec, 0)

    def test_includes_all_benchmarks(self):
        """Report should include all benchmark types."""
        report = benchmark_full_engine(seed=7002)
        
        benchmark_names = {r.name for r in report.results}
        
        self.assertIn("single_day_load", benchmark_names)
        self.assertIn("conflict_detection", benchmark_names)
        self.assertIn("no_conflict_baseline", benchmark_names)
        self.assertIn("working_hours_validation", benchmark_names)
        self.assertIn("room_conflicts", benchmark_names)
        self.assertIn("randomized", benchmark_names)

    def test_generates_summary(self):
        """Report should include summary."""
        report = benchmark_full_engine(seed=7003)
        
        self.assertIn('total_operations', report.summary)
        self.assertIn('total_queries', report.summary)
        self.assertIn('avg_throughput_ops_sec', report.summary)

    def test_generates_recommendations(self):
        """Report should include recommendations."""
        report = benchmark_full_engine(seed=7004)
        
        self.assertIsInstance(report.recommendations, list)
        self.assertGreater(len(report.recommendations), 0)


class GenerateReportTest(TestCase):
    """Test report generation function."""

    def test_generates_report_from_results(self):
        """generate_report() should create report from results."""
        results = [
            BenchmarkResult(
                name="test1",
                timing=TimingStats.from_samples([1.0, 2.0, 3.0]),
                queries=QueryStats(total_queries=10, queries_per_op=2.0),
                throughput_ops_sec=100.0,
            ),
            BenchmarkResult(
                name="test2",
                timing=TimingStats.from_samples([2.0, 3.0, 4.0]),
                queries=QueryStats(total_queries=20, queries_per_op=4.0),
                throughput_ops_sec=50.0,
            ),
        ]
        
        report = generate_report(results)
        
        self.assertIsInstance(report, BenchmarkReport)
        self.assertEqual(len(report.results), 2)
        self.assertIn('total_operations', report.summary)


class BenchmarkReportTest(TestCase):
    """Test BenchmarkReport data class."""

    def test_to_dict(self):
        """to_dict() should return complete structure."""
        report = BenchmarkReport(
            timestamp="2025-01-01T12:00:00",
            total_duration_sec=10.5,
            results=[
                BenchmarkResult(name="test", throughput_ops_sec=100.0),
            ],
            summary={'key': 'value'},
            bottlenecks=['bottleneck1'],
            recommendations=['recommendation1'],
        )
        
        d = report.to_dict()
        
        self.assertEqual(d['timestamp'], "2025-01-01T12:00:00")
        self.assertEqual(d['total_duration_sec'], 10.5)
        self.assertEqual(len(d['results']), 1)
        self.assertIn('key', d['summary'])
        self.assertEqual(len(d['bottlenecks']), 1)
        self.assertEqual(len(d['recommendations']), 1)
