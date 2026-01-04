"""
Appointments Services Module.

This package contains service-layer logic for the appointments app:
- scheduling: Core scheduling logic (conflict detection, validation)
- scheduling_simulation: Simulation of scheduling conflicts for testing
- scheduling_benchmark: Performance benchmarks for the scheduling engine
- scheduling_conflict_report: Conflict report generation and analysis
- scheduling_visualization: Text-based visualization of conflicts
"""

from praxi_backend.appointments.services.scheduling_benchmark import (
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
from praxi_backend.appointments.services.scheduling_conflict_report import (
    ConflictCategory,
    ConflictDetail,
    ConflictExample,
    ConflictGroup,
    ConflictPriority,
    ConflictReport,
    ConflictSummary,
    ReportContext,
    format_text_report,
    generate_conflict_report,
    get_conflict_types_overview,
    print_conflict_report,
)
from praxi_backend.appointments.services.scheduling_simulation import (
    SimulationContext,
    SimulationResult,
    SimulationSummary,
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
from praxi_backend.appointments.services.scheduling_visualization import (
    VisualizationContext,
    generate_conflict_visualization,
    print_conflict_visualization,
    create_conflict_table,
    create_hourly_heatmap,
    create_doctor_heatmap,
    create_room_heatmap,
    create_summary,
    visualize_doctor_conflicts,
    visualize_room_conflicts,
    visualize_absences,
    visualize_working_hours,
    visualize_edge_cases,
)
from praxi_backend.appointments.services.scheduling_dashboard import (
    DashboardContext,
    DashboardStats,
    DoctorStats,
    RoomStats,
    generate_dashboard,
    generate_daily_overview,
    generate_weekly_overview,
    generate_conflict_summary,
    generate_resource_summary,
    generate_kpis,
    generate_recommendations,
    print_dashboard,
)

__all__ = [
    # Simulation Classes
    "SimulationContext",
    "SimulationResult",
    "SimulationSummary",
    # Simulation Runner
    "run_all_simulations",
    # Simulation Functions
    "simulate_doctor_conflict",
    "simulate_room_conflict",
    "simulate_device_conflict",
    "simulate_appointment_overlap",
    "simulate_operation_overlap",
    "simulate_working_hours_violation",
    "simulate_doctor_absence",
    "simulate_doctor_break",
    "simulate_patient_double_booking",
    "simulate_team_conflict",
    "simulate_edge_cases",
    "simulate_full_day_load",
    "simulate_randomized_day",
    # Benchmark Classes
    "BenchmarkContext",
    "BenchmarkReport",
    "BenchmarkResult",
    "QueryStats",
    "TimingStats",
    # Benchmark Functions
    "benchmark_single_day_load",
    "benchmark_conflict_detection",
    "benchmark_no_conflict",
    "benchmark_working_hours_validation",
    "benchmark_room_conflicts",
    "benchmark_randomized",
    "benchmark_full_engine",
    "generate_report",
    "print_benchmark_report",
    # Conflict Report Classes
    "ConflictCategory",
    "ConflictDetail",
    "ConflictExample",
    "ConflictGroup",
    "ConflictPriority",
    "ConflictReport",
    "ConflictSummary",
    "ReportContext",
    # Conflict Report Functions
    "format_text_report",
    "generate_conflict_report",
    "get_conflict_types_overview",
    "print_conflict_report",
    # Visualization Classes
    "VisualizationContext",
    # Visualization Functions
    "generate_conflict_visualization",
    "print_conflict_visualization",
    "create_conflict_table",
    "create_hourly_heatmap",
    "create_doctor_heatmap",
    "create_room_heatmap",
    "create_summary",
    "visualize_doctor_conflicts",
    "visualize_room_conflicts",
    "visualize_absences",
    "visualize_working_hours",
    "visualize_edge_cases",
    # Dashboard Classes
    "DashboardContext",
    "DashboardStats",
    "DoctorStats",
    "RoomStats",
    # Dashboard Functions
    "generate_dashboard",
    "generate_daily_overview",
    "generate_weekly_overview",
    "generate_conflict_summary",
    "generate_resource_summary",
    "generate_kpis",
    "generate_recommendations",
    "print_dashboard",
]
