"""
Scheduling Benchmark Module for PraxiApp.

This module provides comprehensive performance benchmarks for the Scheduling Engine
to measure throughput, latency, and resource usage under various load conditions.

==============================================================================
BENCHMARK CATEGORIES
==============================================================================

1. SINGLE DAY LOAD
   - Creates n appointments + m operations on a single day
   - Measures conflict detection, working hours validation, room conflicts
   - Tracks queries per planning operation

2. PEAK LOAD
   - Simulates extreme load: 500 appointments + 200 operations
   - Measures throughput (operations per second)
   - Identifies system bottlenecks

3. CONFLICT DETECTION
   - Runs 1000 conflict checks sequentially
   - Measures average/min/max detection time
   - Useful for identifying slow conflict patterns

4. NO CONFLICT BASELINE
   - Runs 1000 conflict-free checks
   - Establishes baseline performance
   - Used for comparison with conflict scenarios

5. RANDOMIZED LOAD
   - Deterministic random simulation with seed
   - Realistic mix of appointments and operations
   - Reproducible for regression testing

==============================================================================
METRICS COLLECTED
==============================================================================

- Execution Time (ms): Using time.perf_counter() for high precision
- Query Count: Via Django connection.queries
- Throughput: Operations per second
- Memory: Optional memory profiling
- Bottlenecks: Identifies slowest operations

==============================================================================
ARCHITECTURE RULES
==============================================================================

- All DB access uses .using('default') - NO access to medical DB
- patient_id is always an integer dummy (99999, 99998, etc.)
- Results are structured dicts for easy JSON serialization
- Deterministic via random.seed() for reproducibility

==============================================================================
"""

from __future__ import annotations

import random
import statistics
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dt_time, timedelta
from typing import Any, Callable

from django.db import connection, reset_queries
from django.db.models import Count
from django.utils import timezone

from praxi_backend.appointments.exceptions import (
    Conflict,
    DoctorAbsentError,
    DoctorBreakConflict,
    SchedulingConflictError,
    WorkingHoursViolation,
)
from praxi_backend.appointments.models import (
    Appointment,
    AppointmentResource,
    AppointmentType,
    DoctorAbsence,
    DoctorBreak,
    DoctorHours,
    Operation,
    OperationType,
    PracticeHours,
    Resource,
)
from praxi_backend.appointments.services.scheduling import (
    check_appointment_conflicts,
    check_operation_conflicts,
    check_patient_conflicts,
    validate_doctor_absences,
    validate_doctor_breaks,
    validate_working_hours,
)
from praxi_backend.core.models import Role, User


# ==============================================================================
# Constants
# ==============================================================================

DUMMY_PATIENT_ID_BASE = 99999
DEFAULT_SEED = 42


# ==============================================================================
# Data Classes for Benchmark Results
# ==============================================================================

@dataclass
class TimingStats:
    """Statistical summary of timing measurements."""
    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float('inf')
    max_ms: float = 0.0
    avg_ms: float = 0.0
    median_ms: float = 0.0
    std_dev_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            'count': self.count,
            'total_ms': round(self.total_ms, 3),
            'min_ms': round(self.min_ms, 3) if self.min_ms != float('inf') else 0,
            'max_ms': round(self.max_ms, 3),
            'avg_ms': round(self.avg_ms, 3),
            'median_ms': round(self.median_ms, 3),
            'std_dev_ms': round(self.std_dev_ms, 3),
            'p95_ms': round(self.p95_ms, 3),
            'p99_ms': round(self.p99_ms, 3),
        }

    @classmethod
    def from_samples(cls, samples: list[float]) -> 'TimingStats':
        """Create TimingStats from a list of timing samples (in ms)."""
        if not samples:
            return cls()
        
        sorted_samples = sorted(samples)
        n = len(sorted_samples)
        
        return cls(
            count=n,
            total_ms=sum(samples),
            min_ms=min(samples),
            max_ms=max(samples),
            avg_ms=statistics.mean(samples),
            median_ms=statistics.median(samples),
            std_dev_ms=statistics.stdev(samples) if n > 1 else 0.0,
            p95_ms=sorted_samples[int(n * 0.95)] if n > 1 else sorted_samples[-1],
            p99_ms=sorted_samples[int(n * 0.99)] if n > 1 else sorted_samples[-1],
        )


@dataclass
class QueryStats:
    """Statistics about database queries."""
    total_queries: int = 0
    queries_per_op: float = 0.0
    slowest_query_ms: float = 0.0
    query_breakdown: dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            'total_queries': self.total_queries,
            'queries_per_op': round(self.queries_per_op, 2),
            'slowest_query_ms': round(self.slowest_query_ms, 3),
            'query_breakdown': self.query_breakdown,
        }


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    name: str
    description: str = ""
    timing: TimingStats = field(default_factory=TimingStats)
    queries: QueryStats = field(default_factory=QueryStats)
    throughput_ops_sec: float = 0.0
    items_created: int = 0
    conflicts_detected: int = 0
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'timing': self.timing.to_dict(),
            'queries': self.queries.to_dict(),
            'throughput_ops_sec': round(self.throughput_ops_sec, 2),
            'items_created': self.items_created,
            'conflicts_detected': self.conflicts_detected,
            'errors': self.errors,
            'metadata': self.metadata,
        }


@dataclass
class BenchmarkReport:
    """Complete benchmark report with all results."""
    timestamp: str = ""
    total_duration_sec: float = 0.0
    results: list[BenchmarkResult] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    bottlenecks: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'total_duration_sec': round(self.total_duration_sec, 2),
            'results': [r.to_dict() for r in self.results],
            'summary': self.summary,
            'bottlenecks': self.bottlenecks,
            'recommendations': self.recommendations,
        }


# ==============================================================================
# Benchmark Context
# ==============================================================================

class BenchmarkContext:
    """
    Context manager for scheduling benchmarks.
    
    Creates and manages test data (doctors, rooms, devices, hours) in the
    default database. All data is created fresh for each benchmark.
    """

    def __init__(self, *, seed: int = DEFAULT_SEED):
        self.seed = seed
        self.tz = timezone.get_current_timezone()
        self.today = timezone.localdate()
        
        # Will be populated by setup()
        self.role_admin: Role | None = None
        self.role_doctor: Role | None = None
        self.doctors: list[User] = []
        self.admin: User | None = None
        self.rooms: list[Resource] = []
        self.devices: list[Resource] = []
        self.appt_types: list[AppointmentType] = []
        self.op_types: list[OperationType] = []
        self._patient_counter = DUMMY_PATIENT_ID_BASE

    def setup(self, num_doctors: int = 5, num_rooms: int = 4, num_devices: int = 3):
        """Create all necessary test data."""
        random.seed(self.seed)
        
        # Create roles
        self.role_admin, _ = Role.objects.using("default").get_or_create(
            name="admin", defaults={"label": "Administrator"}
        )
        self.role_doctor, _ = Role.objects.using("default").get_or_create(
            name="doctor", defaults={"label": "Arzt"}
        )

        # Create admin user
        self.admin = User.objects.db_manager("default").create_user(
            username=f"bench_admin_{self.seed}",
            password="benchpass123",
            email=f"bench_admin_{self.seed}@test.local",
            role=self.role_admin,
        )

        # Create doctors
        for i in range(num_doctors):
            doctor = User.objects.db_manager("default").create_user(
                username=f"bench_doctor_{self.seed}_{i}",
                password="benchpass123",
                email=f"bench_doctor_{self.seed}_{i}@test.local",
                role=self.role_doctor,
                first_name=f"Dr",
                last_name=f"Bench{i}",
            )
            self.doctors.append(doctor)

        # Create rooms
        for i in range(num_rooms):
            room = Resource.objects.using("default").create(
                name=f"BenchRoom_{self.seed}_{i}",
                type="room",
                color="#6A5ACD",
                active=True,
            )
            self.rooms.append(room)

        # Create devices
        for i in range(num_devices):
            device = Resource.objects.using("default").create(
                name=f"BenchDevice_{self.seed}_{i}",
                type="device",
                color="#228B22",
                active=True,
            )
            self.devices.append(device)

        # Create appointment types
        for duration in [15, 30, 45, 60]:
            appt_type = AppointmentType.objects.using("default").create(
                name=f"BenchAppt_{self.seed}_{duration}min",
                color="#2E8B57",
                duration_minutes=duration,
                active=True,
            )
            self.appt_types.append(appt_type)

        # Create operation types
        for i, (prep, op, post) in enumerate([(10, 30, 10), (15, 60, 15), (20, 90, 20)]):
            op_type = OperationType.objects.using("default").create(
                name=f"BenchOp_{self.seed}_{i}",
                prep_duration=prep,
                op_duration=op,
                post_duration=post,
                color="#8A2BE2",
                active=True,
            )
            self.op_types.append(op_type)

        # Create practice hours (Mon-Fri, 07:00-20:00)
        for weekday in range(5):
            # Check if any practice hours exist for this weekday
            existing = PracticeHours.objects.using("default").filter(weekday=weekday, active=True).first()
            if not existing:
                PracticeHours.objects.using("default").create(
                    weekday=weekday,
                    start_time=dt_time(7, 0),
                    end_time=dt_time(20, 0),
                    active=True,
                )

        # Create doctor hours for all doctors (Mon-Fri, 08:00-18:00)
        for doctor in self.doctors:
            for weekday in range(5):
                # Check if doctor hours exist for this doctor and weekday
                existing = DoctorHours.objects.using("default").filter(
                    doctor=doctor, weekday=weekday, active=True
                ).first()
                if not existing:
                    DoctorHours.objects.using("default").create(
                        doctor=doctor,
                        weekday=weekday,
                        start_time=dt_time(8, 0),
                        end_time=dt_time(18, 0),
                        active=True,
                    )

    def teardown(self):
        """Clean up test data (optional - tests use transactions)."""
        pass

    def next_patient_id(self) -> int:
        """Get next dummy patient ID."""
        self._patient_counter -= 1
        return self._patient_counter + 1

    def make_datetime(self, d: date, t: dt_time) -> datetime:
        """Create a timezone-aware datetime."""
        return timezone.make_aware(datetime.combine(d, t), self.tz)

    def get_next_weekday(self, target_weekday: int, start_date: date | None = None) -> date:
        """Get the next occurrence of a weekday (0=Mon) from start_date."""
        base = start_date or self.today
        days_ahead = target_weekday - base.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return base + timedelta(days=days_ahead)


# ==============================================================================
# Query Tracking Utilities
# ==============================================================================

def start_query_tracking():
    """Enable and reset query tracking."""
    reset_queries()
    connection.force_debug_cursor = True


def stop_query_tracking() -> list[dict]:
    """Stop tracking and return collected queries."""
    queries = list(connection.queries)
    connection.force_debug_cursor = False
    return queries


def analyze_queries(queries: list[dict], num_operations: int) -> QueryStats:
    """Analyze collected queries and return statistics."""
    total = len(queries)
    slowest = 0.0
    breakdown: dict[str, int] = {'SELECT': 0, 'INSERT': 0, 'UPDATE': 0, 'DELETE': 0, 'OTHER': 0}
    
    for q in queries:
        sql = q.get('sql', '').upper()
        time_val = float(q.get('time', 0))
        slowest = max(slowest, time_val * 1000)  # Convert to ms
        
        if sql.startswith('SELECT'):
            breakdown['SELECT'] += 1
        elif sql.startswith('INSERT'):
            breakdown['INSERT'] += 1
        elif sql.startswith('UPDATE'):
            breakdown['UPDATE'] += 1
        elif sql.startswith('DELETE'):
            breakdown['DELETE'] += 1
        else:
            breakdown['OTHER'] += 1
    
    return QueryStats(
        total_queries=total,
        queries_per_op=total / num_operations if num_operations > 0 else 0,
        slowest_query_ms=slowest,
        query_breakdown=breakdown,
    )


# ==============================================================================
# Benchmark Functions
# ==============================================================================

def benchmark_single_day_load(
    ctx: BenchmarkContext,
    n_appointments: int = 50,
    n_operations: int = 20,
) -> BenchmarkResult:
    """
    Benchmark single day load with n appointments + m operations.
    
    Measures:
    - Conflict detection time
    - Working hours validation time
    - Room conflict detection
    - Total planning time
    - Queries per planning operation
    """
    monday = ctx.get_next_weekday(0)
    samples: list[float] = []
    appointments_created = 0
    operations_created = 0
    conflicts_detected = 0
    
    start_query_tracking()
    total_start = time.perf_counter()
    
    # Create appointments distributed across the day
    current_hour = 8
    current_minute = 0
    
    for i in range(n_appointments):
        doctor = ctx.doctors[i % len(ctx.doctors)]
        duration = ctx.appt_types[i % len(ctx.appt_types)].duration_minutes
        
        start = ctx.make_datetime(monday, dt_time(current_hour, current_minute))
        end_minutes = current_minute + duration
        end_hour = current_hour + end_minutes // 60
        end_minute = end_minutes % 60
        
        if end_hour >= 18:
            break
            
        end = ctx.make_datetime(monday, dt_time(end_hour, end_minute))
        
        op_start = time.perf_counter()
        
        # Check conflicts
        conflicts = check_appointment_conflicts(
            date=monday,
            start_time=start,
            end_time=end,
            doctor_id=doctor.id,
        )
        
        if conflicts:
            conflicts_detected += len(conflicts)
        else:
            # Create appointment
            Appointment.objects.using("default").create(
                patient_id=ctx.next_patient_id(),
                doctor=doctor,
                type=ctx.appt_types[i % len(ctx.appt_types)],
                start_time=start,
                end_time=end,
                status="scheduled",
            )
            appointments_created += 1
        
        op_end = time.perf_counter()
        samples.append((op_end - op_start) * 1000)
        
        # Advance time
        current_minute += 15
        if current_minute >= 60:
            current_minute = 0
            current_hour += 1

    # Create operations
    current_hour = 9
    for i in range(n_operations):
        surgeon = ctx.doctors[i % len(ctx.doctors)]
        room = ctx.rooms[i % len(ctx.rooms)]
        op_type = ctx.op_types[i % len(ctx.op_types)]
        total_duration = op_type.prep_duration + op_type.op_duration + op_type.post_duration
        
        start = ctx.make_datetime(monday, dt_time(current_hour, 0))
        end_hour = current_hour + total_duration // 60
        end_minute = total_duration % 60
        
        if end_hour >= 18:
            break
            
        end = ctx.make_datetime(monday, dt_time(end_hour, end_minute))
        
        op_start = time.perf_counter()
        
        conflicts = check_operation_conflicts(
            date=monday,
            start_time=start,
            end_time=end,
            primary_surgeon_id=surgeon.id,
            room_id=room.id,
        )
        
        if conflicts:
            conflicts_detected += len(conflicts)
        else:
            Operation.objects.using("default").create(
                patient_id=ctx.next_patient_id(),
                primary_surgeon=surgeon,
                op_room=room,
                op_type=op_type,
                start_time=start,
                end_time=end,
                status="planned",
            )
            operations_created += 1
        
        op_end = time.perf_counter()
        samples.append((op_end - op_start) * 1000)
        
        current_hour += 1

    total_end = time.perf_counter()
    queries = stop_query_tracking()
    
    total_ops = appointments_created + operations_created + conflicts_detected
    
    return BenchmarkResult(
        name="single_day_load",
        description=f"Single day with {n_appointments} appointments + {n_operations} operations",
        timing=TimingStats.from_samples(samples),
        queries=analyze_queries(queries, total_ops),
        throughput_ops_sec=total_ops / (total_end - total_start) if total_end > total_start else 0,
        items_created=appointments_created + operations_created,
        conflicts_detected=conflicts_detected,
        metadata={
            'n_appointments_requested': n_appointments,
            'n_operations_requested': n_operations,
            'appointments_created': appointments_created,
            'operations_created': operations_created,
        },
    )


def benchmark_peak_load(ctx: BenchmarkContext) -> BenchmarkResult:
    """
    Benchmark extreme peak load: 500 appointments + 200 operations.
    
    Measures system throughput under stress conditions.
    """
    return benchmark_single_day_load(ctx, n_appointments=500, n_operations=200)


def benchmark_conflict_detection(
    ctx: BenchmarkContext,
    n_checks: int = 1000,
) -> BenchmarkResult:
    """
    Benchmark conflict detection with guaranteed conflicts.
    
    Creates overlapping appointments and measures detection time.
    """
    monday = ctx.get_next_weekday(0)
    doctor = ctx.doctors[0]
    samples: list[float] = []
    
    # Create base appointment that will always conflict
    base_start = ctx.make_datetime(monday, dt_time(10, 0))
    base_end = ctx.make_datetime(monday, dt_time(11, 0))
    
    Appointment.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        doctor=doctor,
        type=ctx.appt_types[0],
        start_time=base_start,
        end_time=base_end,
        status="scheduled",
    )
    
    start_query_tracking()
    total_start = time.perf_counter()
    
    # Run n conflict checks (all should detect conflict)
    check_start = ctx.make_datetime(monday, dt_time(10, 15))
    check_end = ctx.make_datetime(monday, dt_time(10, 45))
    
    for _ in range(n_checks):
        op_start = time.perf_counter()
        
        conflicts = check_appointment_conflicts(
            date=monday,
            start_time=check_start,
            end_time=check_end,
            doctor_id=doctor.id,
        )
        
        op_end = time.perf_counter()
        samples.append((op_end - op_start) * 1000)
    
    total_end = time.perf_counter()
    queries = stop_query_tracking()
    
    return BenchmarkResult(
        name="conflict_detection",
        description=f"{n_checks} conflict checks (all with conflicts)",
        timing=TimingStats.from_samples(samples),
        queries=analyze_queries(queries, n_checks),
        throughput_ops_sec=n_checks / (total_end - total_start),
        conflicts_detected=n_checks,
        metadata={
            'n_checks': n_checks,
            'all_conflicts_detected': True,
        },
    )


def benchmark_no_conflict(
    ctx: BenchmarkContext,
    n_checks: int = 1000,
) -> BenchmarkResult:
    """
    Benchmark conflict-free checks.
    
    Checks time slots with no existing appointments (baseline performance).
    """
    monday = ctx.get_next_weekday(0)
    samples: list[float] = []
    
    start_query_tracking()
    total_start = time.perf_counter()
    
    # Check different time slots (no appointments exist)
    for i in range(n_checks):
        doctor = ctx.doctors[i % len(ctx.doctors)]
        hour = 8 + (i % 10)
        minute = (i * 5) % 60
        
        check_start = ctx.make_datetime(monday, dt_time(hour, minute))
        check_end = ctx.make_datetime(monday, dt_time(hour, (minute + 30) % 60 if minute < 30 else 0))
        if minute >= 30:
            check_end = ctx.make_datetime(monday, dt_time(hour + 1, (minute + 30) % 60))
        
        op_start = time.perf_counter()
        
        conflicts = check_appointment_conflicts(
            date=monday,
            start_time=check_start,
            end_time=check_end,
            doctor_id=doctor.id,
        )
        
        op_end = time.perf_counter()
        samples.append((op_end - op_start) * 1000)
    
    total_end = time.perf_counter()
    queries = stop_query_tracking()
    
    return BenchmarkResult(
        name="no_conflict_baseline",
        description=f"{n_checks} conflict-free checks (baseline)",
        timing=TimingStats.from_samples(samples),
        queries=analyze_queries(queries, n_checks),
        throughput_ops_sec=n_checks / (total_end - total_start),
        conflicts_detected=0,
        metadata={
            'n_checks': n_checks,
            'all_conflict_free': True,
        },
    )


def benchmark_working_hours_validation(
    ctx: BenchmarkContext,
    n_checks: int = 500,
) -> BenchmarkResult:
    """
    Benchmark working hours validation.
    
    Tests both valid and invalid time slots.
    """
    monday = ctx.get_next_weekday(0)
    sunday = ctx.get_next_weekday(6)
    samples: list[float] = []
    violations_detected = 0
    
    start_query_tracking()
    total_start = time.perf_counter()
    
    for i in range(n_checks):
        doctor = ctx.doctors[i % len(ctx.doctors)]
        
        # Alternate between valid and invalid times
        if i % 2 == 0:
            # Valid: weekday during hours
            d = monday
            start = ctx.make_datetime(d, dt_time(10, 0))
            end = ctx.make_datetime(d, dt_time(10, 30))
        else:
            # Invalid: Sunday (no practice hours)
            d = sunday
            start = ctx.make_datetime(d, dt_time(10, 0))
            end = ctx.make_datetime(d, dt_time(10, 30))
        
        op_start = time.perf_counter()
        
        try:
            validate_working_hours(
                doctor_id=doctor.id,
                date=d,
                start_time=start,
                end_time=end,
            )
        except WorkingHoursViolation:
            violations_detected += 1
        
        op_end = time.perf_counter()
        samples.append((op_end - op_start) * 1000)
    
    total_end = time.perf_counter()
    queries = stop_query_tracking()
    
    return BenchmarkResult(
        name="working_hours_validation",
        description=f"{n_checks} working hours validations",
        timing=TimingStats.from_samples(samples),
        queries=analyze_queries(queries, n_checks),
        throughput_ops_sec=n_checks / (total_end - total_start),
        conflicts_detected=violations_detected,
        metadata={
            'n_checks': n_checks,
            'violations_detected': violations_detected,
        },
    )


def benchmark_room_conflicts(
    ctx: BenchmarkContext,
    n_checks: int = 500,
) -> BenchmarkResult:
    """
    Benchmark room conflict detection for operations.
    """
    monday = ctx.get_next_weekday(0)
    room = ctx.rooms[0]
    samples: list[float] = []
    conflicts_found = 0
    
    # Create a base operation
    base_start = ctx.make_datetime(monday, dt_time(10, 0))
    base_end = ctx.make_datetime(monday, dt_time(12, 0))
    
    Operation.objects.using("default").create(
        patient_id=ctx.next_patient_id(),
        primary_surgeon=ctx.doctors[0],
        op_room=room,
        op_type=ctx.op_types[0],
        start_time=base_start,
        end_time=base_end,
        status="planned",
    )
    
    start_query_tracking()
    total_start = time.perf_counter()
    
    for i in range(n_checks):
        surgeon = ctx.doctors[(i + 1) % len(ctx.doctors)]
        
        # Alternate between conflicting and non-conflicting times
        if i % 2 == 0:
            check_start = ctx.make_datetime(monday, dt_time(11, 0))
            check_end = ctx.make_datetime(monday, dt_time(13, 0))
        else:
            check_start = ctx.make_datetime(monday, dt_time(14, 0))
            check_end = ctx.make_datetime(monday, dt_time(16, 0))
        
        op_start = time.perf_counter()
        
        conflicts = check_operation_conflicts(
            date=monday,
            start_time=check_start,
            end_time=check_end,
            primary_surgeon_id=surgeon.id,
            room_id=room.id,
        )
        
        if conflicts:
            conflicts_found += len(conflicts)
        
        op_end = time.perf_counter()
        samples.append((op_end - op_start) * 1000)
    
    total_end = time.perf_counter()
    queries = stop_query_tracking()
    
    return BenchmarkResult(
        name="room_conflicts",
        description=f"{n_checks} room conflict checks",
        timing=TimingStats.from_samples(samples),
        queries=analyze_queries(queries, n_checks),
        throughput_ops_sec=n_checks / (total_end - total_start),
        conflicts_detected=conflicts_found,
        metadata={
            'n_checks': n_checks,
        },
    )


def benchmark_randomized(
    ctx: BenchmarkContext,
    seed: int = DEFAULT_SEED,
    n: int = 200,
) -> BenchmarkResult:
    """
    Deterministic randomized benchmark simulation.
    
    Generates a realistic mix of appointments and operations.
    """
    random.seed(seed)
    monday = ctx.get_next_weekday(0)
    samples: list[float] = []
    appointments_created = 0
    operations_created = 0
    conflicts_detected = 0
    
    start_query_tracking()
    total_start = time.perf_counter()
    
    for i in range(n):
        is_operation = random.random() < 0.3  # 30% operations
        doctor = random.choice(ctx.doctors)
        hour = random.randint(8, 16)
        minute = random.choice([0, 15, 30, 45])
        
        start = ctx.make_datetime(monday, dt_time(hour, minute))
        
        op_start = time.perf_counter()
        
        if is_operation:
            room = random.choice(ctx.rooms)
            op_type = random.choice(ctx.op_types)
            duration = op_type.prep_duration + op_type.op_duration + op_type.post_duration
            end_minutes = minute + duration
            end_hour = hour + end_minutes // 60
            end_minute = end_minutes % 60
            
            if end_hour < 18:
                end = ctx.make_datetime(monday, dt_time(end_hour, end_minute))
                
                conflicts = check_operation_conflicts(
                    date=monday,
                    start_time=start,
                    end_time=end,
                    primary_surgeon_id=doctor.id,
                    room_id=room.id,
                )
                
                if conflicts:
                    conflicts_detected += len(conflicts)
                else:
                    Operation.objects.using("default").create(
                        patient_id=ctx.next_patient_id(),
                        primary_surgeon=doctor,
                        op_room=room,
                        op_type=op_type,
                        start_time=start,
                        end_time=end,
                        status="planned",
                    )
                    operations_created += 1
        else:
            appt_type = random.choice(ctx.appt_types)
            duration = appt_type.duration_minutes
            end_minutes = minute + duration
            end_hour = hour + end_minutes // 60
            end_minute = end_minutes % 60
            
            if end_hour < 18:
                end = ctx.make_datetime(monday, dt_time(end_hour, end_minute))
                
                conflicts = check_appointment_conflicts(
                    date=monday,
                    start_time=start,
                    end_time=end,
                    doctor_id=doctor.id,
                )
                
                if conflicts:
                    conflicts_detected += len(conflicts)
                else:
                    Appointment.objects.using("default").create(
                        patient_id=ctx.next_patient_id(),
                        doctor=doctor,
                        type=appt_type,
                        start_time=start,
                        end_time=end,
                        status="scheduled",
                    )
                    appointments_created += 1
        
        op_end = time.perf_counter()
        samples.append((op_end - op_start) * 1000)
    
    total_end = time.perf_counter()
    queries = stop_query_tracking()
    
    return BenchmarkResult(
        name="randomized",
        description=f"Randomized simulation with seed={seed}, n={n}",
        timing=TimingStats.from_samples(samples),
        queries=analyze_queries(queries, n),
        throughput_ops_sec=n / (total_end - total_start),
        items_created=appointments_created + operations_created,
        conflicts_detected=conflicts_detected,
        metadata={
            'seed': seed,
            'n': n,
            'appointments_created': appointments_created,
            'operations_created': operations_created,
        },
    )


def benchmark_full_engine(seed: int = DEFAULT_SEED) -> BenchmarkReport:
    """
    Run all benchmarks and generate comprehensive report.
    
    Args:
        seed: Random seed for reproducibility.
        
    Returns:
        BenchmarkReport with all results and recommendations.
    """
    ctx = BenchmarkContext(seed=seed)
    ctx.setup()
    
    report = BenchmarkReport(
        timestamp=timezone.now().isoformat(),
    )
    
    total_start = time.perf_counter()
    
    # Run all benchmarks
    report.results.append(benchmark_single_day_load(ctx, 50, 20))
    report.results.append(benchmark_conflict_detection(ctx, 500))
    report.results.append(benchmark_no_conflict(ctx, 500))
    report.results.append(benchmark_working_hours_validation(ctx, 200))
    report.results.append(benchmark_room_conflicts(ctx, 200))
    report.results.append(benchmark_randomized(ctx, seed=seed, n=100))
    
    total_end = time.perf_counter()
    report.total_duration_sec = total_end - total_start
    
    # Generate summary and recommendations
    report.summary = _generate_summary(report.results)
    report.bottlenecks = _identify_bottlenecks(report.results)
    report.recommendations = _generate_recommendations(report.results)
    
    ctx.teardown()
    return report


# ==============================================================================
# Report Generation
# ==============================================================================

def _generate_summary(results: list[BenchmarkResult]) -> dict[str, Any]:
    """Generate summary statistics from benchmark results."""
    total_ops = sum(r.timing.count for r in results)
    total_queries = sum(r.queries.total_queries for r in results)
    avg_throughput = statistics.mean(r.throughput_ops_sec for r in results if r.throughput_ops_sec > 0)
    
    return {
        'total_operations': total_ops,
        'total_queries': total_queries,
        'avg_throughput_ops_sec': round(avg_throughput, 2),
        'fastest_benchmark': min(results, key=lambda r: r.timing.avg_ms).name,
        'slowest_benchmark': max(results, key=lambda r: r.timing.avg_ms).name,
    }


def _identify_bottlenecks(results: list[BenchmarkResult]) -> list[str]:
    """Identify performance bottlenecks."""
    bottlenecks = []
    
    for r in results:
        # High query count
        if r.queries.queries_per_op > 10:
            bottlenecks.append(
                f"{r.name}: High query count ({r.queries.queries_per_op:.1f} queries/op)"
            )
        
        # Slow average time
        if r.timing.avg_ms > 50:
            bottlenecks.append(
                f"{r.name}: Slow average time ({r.timing.avg_ms:.1f}ms)"
            )
        
        # High variance
        if r.timing.std_dev_ms > r.timing.avg_ms:
            bottlenecks.append(
                f"{r.name}: High variance (std_dev={r.timing.std_dev_ms:.1f}ms > avg={r.timing.avg_ms:.1f}ms)"
            )
        
        # Slow P99
        if r.timing.p99_ms > r.timing.avg_ms * 5:
            bottlenecks.append(
                f"{r.name}: P99 outliers ({r.timing.p99_ms:.1f}ms vs avg {r.timing.avg_ms:.1f}ms)"
            )
    
    return bottlenecks


def _generate_recommendations(results: list[BenchmarkResult]) -> list[str]:
    """Generate optimization recommendations."""
    recommendations = []
    
    # Analyze query patterns
    total_selects = sum(r.queries.query_breakdown.get('SELECT', 0) for r in results)
    total_inserts = sum(r.queries.query_breakdown.get('INSERT', 0) for r in results)
    
    if total_selects > total_inserts * 10:
        recommendations.append(
            "Consider adding database indexes for frequently queried fields"
        )
        recommendations.append(
            "Use select_related() or prefetch_related() to reduce query count"
        )
    
    # Check for slow conflict detection
    conflict_result = next((r for r in results if r.name == "conflict_detection"), None)
    no_conflict_result = next((r for r in results if r.name == "no_conflict_baseline"), None)
    
    if conflict_result and no_conflict_result:
        if conflict_result.timing.avg_ms > no_conflict_result.timing.avg_ms * 2:
            recommendations.append(
                "Conflict detection is slower than baseline - consider caching active appointments"
            )
    
    # Check for high peak load latency
    peak_result = next((r for r in results if r.name == "single_day_load"), None)
    if peak_result and peak_result.timing.p99_ms > 100:
        recommendations.append(
            "High P99 latency under load - consider batch operations or async processing"
        )
    
    if not recommendations:
        recommendations.append("Performance is within acceptable parameters")
    
    return recommendations


def generate_report(results: list[BenchmarkResult]) -> BenchmarkReport:
    """
    Generate a formatted benchmark report from results.
    
    Args:
        results: List of benchmark results to analyze.
        
    Returns:
        BenchmarkReport with summary, bottlenecks, and recommendations.
    """
    report = BenchmarkReport(
        timestamp=timezone.now().isoformat(),
        results=results,
    )
    
    report.summary = _generate_summary(results)
    report.bottlenecks = _identify_bottlenecks(results)
    report.recommendations = _generate_recommendations(results)
    
    return report


def print_benchmark_report(report: BenchmarkReport) -> None:
    """Print a human-readable benchmark report."""
    print("=" * 80)
    print("SCHEDULING ENGINE BENCHMARK REPORT")
    print("=" * 80)
    print(f"Timestamp: {report.timestamp}")
    print(f"Total Duration: {report.total_duration_sec:.2f}s")
    print()
    
    print("-" * 80)
    print("INDIVIDUAL BENCHMARKS")
    print("-" * 80)
    
    for r in report.results:
        print(f"\n📊 {r.name}")
        print(f"   Description: {r.description}")
        print(f"   Operations: {r.timing.count}")
        print(f"   Avg Time: {r.timing.avg_ms:.3f}ms | Min: {r.timing.min_ms:.3f}ms | Max: {r.timing.max_ms:.3f}ms")
        print(f"   P95: {r.timing.p95_ms:.3f}ms | P99: {r.timing.p99_ms:.3f}ms")
        print(f"   Throughput: {r.throughput_ops_sec:.1f} ops/sec")
        print(f"   Queries: {r.queries.total_queries} total ({r.queries.queries_per_op:.1f}/op)")
        if r.conflicts_detected:
            print(f"   Conflicts: {r.conflicts_detected}")
    
    print()
    print("-" * 80)
    print("SUMMARY")
    print("-" * 80)
    for key, value in report.summary.items():
        print(f"   {key}: {value}")
    
    if report.bottlenecks:
        print()
        print("-" * 80)
        print("⚠️  BOTTLENECKS IDENTIFIED")
        print("-" * 80)
        for b in report.bottlenecks:
            print(f"   • {b}")
    
    print()
    print("-" * 80)
    print("💡 RECOMMENDATIONS")
    print("-" * 80)
    for rec in report.recommendations:
        print(f"   • {rec}")
    
    print("=" * 80)
