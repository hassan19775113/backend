"""
Test Suite for Scheduling Conflict Report Module.

Tests the conflict report generation, grouping, prioritization, and formatting.

==============================================================================
ARCHITECTURE RULES (from copilot-instructions.md)
==============================================================================

- databases = {"default"} on test classes
- Use .using("default") on all ORM calls
- patient_id is an integer (NO ForeignKey to medical.Patient)
- Fully qualified imports: praxi_backend.appointments.*

==============================================================================
"""

from django.test import TestCase
from django.utils import timezone

from praxi_backend.appointments.services.scheduling_conflict_report import (
    ConflictCategory,
    ConflictDetail,
    ConflictExample,
    ConflictGroup,
    ConflictPriority,
    ConflictReport,
    ConflictSummary,
    ReportContext,
    detect_doctor_absence,
    detect_doctor_conflict,
    detect_edge_case_negative_duration,
    detect_edge_case_zero_duration,
    detect_operation_overlap,
    detect_room_conflict,
    detect_working_hours_violation,
    format_text_report,
    generate_conflict_examples,
    generate_conflict_report,
    generate_summary,
    get_conflict_types_overview,
    group_conflicts_by_doctor,
    group_conflicts_by_priority,
    group_conflicts_by_room,
    group_conflicts_by_type,
)


class ConflictPriorityTest(TestCase):
    """Test ConflictPriority enum."""

    def test_priority_values(self):
        """Priority enum should have correct values."""
        self.assertEqual(ConflictPriority.HIGH.value, "high")
        self.assertEqual(ConflictPriority.MEDIUM.value, "medium")
        self.assertEqual(ConflictPriority.LOW.value, "low")


class ConflictCategoryTest(TestCase):
    """Test ConflictCategory enum."""

    def test_category_values(self):
        """Category enum should have correct values."""
        self.assertEqual(ConflictCategory.DOCTOR_CONFLICT.value, "doctor_conflict")
        self.assertEqual(ConflictCategory.ROOM_CONFLICT.value, "room_conflict")
        self.assertEqual(ConflictCategory.WORKING_HOURS_VIOLATION.value, "working_hours_violation")


class ConflictDetailTest(TestCase):
    """Test ConflictDetail data class."""

    def test_to_dict(self):
        """to_dict() should return complete structure."""
        detail = ConflictDetail(
            id="CONF-001",
            category=ConflictCategory.DOCTOR_CONFLICT,
            priority=ConflictPriority.HIGH,
            description="Test conflict",
            affected_objects=[{"type": "Appointment", "id": 1}],
            time_window={"date": "2025-01-01"},
            doctor_id=1,
            doctor_name="Dr. Test",
            cause="Test cause",
            recommendation="Test recommendation",
        )
        
        d = detail.to_dict()
        
        self.assertEqual(d['id'], "CONF-001")
        self.assertEqual(d['category'], "doctor_conflict")
        self.assertEqual(d['priority'], "high")
        self.assertEqual(d['description'], "Test conflict")
        self.assertEqual(d['doctor_name'], "Dr. Test")


class ConflictGroupTest(TestCase):
    """Test ConflictGroup data class."""

    def test_to_dict(self):
        """to_dict() should return correct structure."""
        group = ConflictGroup(
            group_key="doctor_conflict",
            group_type="by_type",
            count=5,
        )
        
        d = group.to_dict()
        
        self.assertEqual(d['group_key'], "doctor_conflict")
        self.assertEqual(d['group_type'], "by_type")
        self.assertEqual(d['count'], 5)


class ConflictSummaryTest(TestCase):
    """Test ConflictSummary data class."""

    def test_to_dict(self):
        """to_dict() should return correct structure."""
        summary = ConflictSummary(
            total_conflicts=10,
            by_category={"doctor_conflict": 5, "room_conflict": 3},
            by_priority={"high": 8, "medium": 2},
            critical_conflicts=8,
            recommendations=["Test recommendation"],
        )
        
        d = summary.to_dict()
        
        self.assertEqual(d['total_conflicts'], 10)
        self.assertEqual(d['critical_conflicts'], 8)
        self.assertIn("doctor_conflict", d['by_category'])


class ReportContextTest(TestCase):
    """Test ReportContext setup."""

    databases = {"default"}

    def test_setup_creates_doctors(self):
        """Context should create doctors."""
        ctx = ReportContext(seed=8001)
        ctx.setup()
        
        self.assertEqual(len(ctx.doctors), 4)

    def test_setup_creates_rooms(self):
        """Context should create rooms."""
        ctx = ReportContext(seed=8002)
        ctx.setup()
        
        self.assertEqual(len(ctx.rooms), 4)

    def test_next_conflict_id_unique(self):
        """Conflict IDs should be unique."""
        ctx = ReportContext(seed=8003)
        
        ids = [ctx.next_conflict_id() for _ in range(5)]
        self.assertEqual(len(set(ids)), 5)


class ConflictTypesOverviewTest(TestCase):
    """Test conflict types overview."""

    def test_returns_all_types(self):
        """Should return all conflict types."""
        overview = get_conflict_types_overview()
        
        self.assertGreaterEqual(len(overview), 10)
        
        types = {ct['type'] for ct in overview}
        self.assertIn("doctor_conflict", types)
        self.assertIn("room_conflict", types)
        self.assertIn("working_hours_violation", types)
        self.assertIn("doctor_absent", types)

    def test_types_have_required_fields(self):
        """Each type should have required fields."""
        overview = get_conflict_types_overview()
        
        for ct in overview:
            self.assertIn('type', ct)
            self.assertIn('name', ct)
            self.assertIn('description', ct)
            self.assertIn('priority', ct)


class DetectDoctorConflictTest(TestCase):
    """Test doctor conflict detection."""

    databases = {"default"}

    def setUp(self):
        self.ctx = ReportContext(seed=8101)
        self.ctx.setup()

    def test_detects_conflict(self):
        """Should detect doctor conflict."""
        conflict = detect_doctor_conflict(self.ctx)
        
        self.assertIsInstance(conflict, ConflictDetail)
        self.assertEqual(conflict.category, ConflictCategory.DOCTOR_CONFLICT)
        self.assertEqual(conflict.priority, ConflictPriority.HIGH)
        self.assertIsNotNone(conflict.doctor_name)


class DetectRoomConflictTest(TestCase):
    """Test room conflict detection."""

    databases = {"default"}

    def setUp(self):
        self.ctx = ReportContext(seed=8102)
        self.ctx.setup()

    def test_detects_conflict(self):
        """Should detect room conflict."""
        conflict = detect_room_conflict(self.ctx)
        
        self.assertIsInstance(conflict, ConflictDetail)
        self.assertEqual(conflict.category, ConflictCategory.ROOM_CONFLICT)
        self.assertEqual(conflict.priority, ConflictPriority.HIGH)
        self.assertIsNotNone(conflict.room_name)


class DetectWorkingHoursViolationTest(TestCase):
    """Test working hours violation detection."""

    databases = {"default"}

    def setUp(self):
        self.ctx = ReportContext(seed=8103)
        self.ctx.setup()

    def test_detects_violation(self):
        """Should detect working hours violation."""
        conflict = detect_working_hours_violation(self.ctx)
        
        self.assertIsInstance(conflict, ConflictDetail)
        self.assertEqual(conflict.category, ConflictCategory.WORKING_HOURS_VIOLATION)
        self.assertEqual(conflict.priority, ConflictPriority.MEDIUM)


class DetectDoctorAbsenceTest(TestCase):
    """Test doctor absence detection."""

    databases = {"default"}

    def setUp(self):
        self.ctx = ReportContext(seed=8104)
        self.ctx.setup()

    def test_detects_absence(self):
        """Should detect doctor absence."""
        conflict = detect_doctor_absence(self.ctx)
        
        self.assertIsInstance(conflict, ConflictDetail)
        self.assertEqual(conflict.category, ConflictCategory.DOCTOR_ABSENT)
        self.assertEqual(conflict.priority, ConflictPriority.MEDIUM)


class DetectOperationOverlapTest(TestCase):
    """Test operation overlap detection."""

    databases = {"default"}

    def setUp(self):
        self.ctx = ReportContext(seed=8105)
        self.ctx.setup()

    def test_detects_overlap(self):
        """Should detect operation overlap."""
        conflict = detect_operation_overlap(self.ctx)
        
        self.assertIsInstance(conflict, ConflictDetail)
        self.assertEqual(conflict.category, ConflictCategory.OPERATION_OVERLAP)
        self.assertEqual(conflict.priority, ConflictPriority.HIGH)


class DetectEdgeCasesTest(TestCase):
    """Test edge case detection."""

    databases = {"default"}

    def setUp(self):
        self.ctx = ReportContext(seed=8106)
        self.ctx.setup()

    def test_detects_zero_duration(self):
        """Should detect zero duration edge case."""
        conflict = detect_edge_case_zero_duration(self.ctx)
        
        self.assertEqual(conflict.category, ConflictCategory.VALIDATION_ERROR)
        self.assertEqual(conflict.priority, ConflictPriority.LOW)
        self.assertIn("Null-Dauer", conflict.description)

    def test_detects_negative_duration(self):
        """Should detect negative duration edge case."""
        conflict = detect_edge_case_negative_duration(self.ctx)
        
        self.assertEqual(conflict.category, ConflictCategory.VALIDATION_ERROR)
        self.assertIn("negative", conflict.description.lower())


class GroupingTest(TestCase):
    """Test conflict grouping functions."""

    def setUp(self):
        self.conflicts = [
            ConflictDetail(
                id="C1",
                category=ConflictCategory.DOCTOR_CONFLICT,
                priority=ConflictPriority.HIGH,
                description="Doctor 1",
                affected_objects=[],
                time_window={},
                doctor_id=1,
                doctor_name="Dr. A",
            ),
            ConflictDetail(
                id="C2",
                category=ConflictCategory.DOCTOR_CONFLICT,
                priority=ConflictPriority.HIGH,
                description="Doctor 2",
                affected_objects=[],
                time_window={},
                doctor_id=1,
                doctor_name="Dr. A",
            ),
            ConflictDetail(
                id="C3",
                category=ConflictCategory.ROOM_CONFLICT,
                priority=ConflictPriority.HIGH,
                description="Room 1",
                affected_objects=[],
                time_window={},
                room_id=1,
                room_name="OP-Saal 1",
            ),
            ConflictDetail(
                id="C4",
                category=ConflictCategory.WORKING_HOURS_VIOLATION,
                priority=ConflictPriority.MEDIUM,
                description="Hours",
                affected_objects=[],
                time_window={},
            ),
        ]

    def test_group_by_type(self):
        """Should group conflicts by type."""
        groups = group_conflicts_by_type(self.conflicts)
        
        self.assertGreater(len(groups), 0)
        # Doctor conflict has 2, should be first
        self.assertEqual(groups[0].group_key, "doctor_conflict")
        self.assertEqual(groups[0].count, 2)

    def test_group_by_priority(self):
        """Should group conflicts by priority."""
        groups = group_conflicts_by_priority(self.conflicts)
        
        # High priority should be first
        self.assertEqual(groups[0].group_key, "high")
        self.assertEqual(groups[0].count, 3)

    def test_group_by_doctor(self):
        """Should group conflicts by doctor."""
        groups = group_conflicts_by_doctor(self.conflicts)
        
        doctor_groups = [g for g in groups if g.group_key == "Dr. A"]
        self.assertEqual(len(doctor_groups), 1)
        self.assertEqual(doctor_groups[0].count, 2)

    def test_group_by_room(self):
        """Should group conflicts by room."""
        groups = group_conflicts_by_room(self.conflicts)
        
        room_groups = [g for g in groups if g.group_key == "OP-Saal 1"]
        self.assertEqual(len(room_groups), 1)


class GenerateConflictExamplesTest(TestCase):
    """Test example generation."""

    databases = {"default"}

    def setUp(self):
        self.ctx = ReportContext(seed=8201)
        self.ctx.setup()

    def test_generates_examples(self):
        """Should generate conflict examples."""
        examples = generate_conflict_examples(self.ctx)
        
        self.assertGreater(len(examples), 0)
        
        # Check for different types
        types = {ex.conflict_type for ex in examples}
        self.assertIn(ConflictCategory.DOCTOR_CONFLICT, types)
        self.assertIn(ConflictCategory.ROOM_CONFLICT, types)

    def test_examples_have_details(self):
        """Examples should have conflict details."""
        examples = generate_conflict_examples(self.ctx)
        
        for ex in examples:
            self.assertIsNotNone(ex.title)
            self.assertIsNotNone(ex.scenario)


class GenerateSummaryTest(TestCase):
    """Test summary generation."""

    def test_generates_summary(self):
        """Should generate summary from conflicts."""
        conflicts = [
            ConflictDetail(
                id="C1",
                category=ConflictCategory.DOCTOR_CONFLICT,
                priority=ConflictPriority.HIGH,
                description="",
                affected_objects=[],
                time_window={},
            ),
            ConflictDetail(
                id="C2",
                category=ConflictCategory.ROOM_CONFLICT,
                priority=ConflictPriority.HIGH,
                description="",
                affected_objects=[],
                time_window={},
            ),
        ]
        
        summary = generate_summary(conflicts)
        
        self.assertEqual(summary.total_conflicts, 2)
        self.assertEqual(summary.critical_conflicts, 2)
        self.assertIn("doctor_conflict", summary.by_category)

    def test_generates_recommendations(self):
        """Should generate recommendations."""
        conflicts = [
            ConflictDetail(
                id="C1",
                category=ConflictCategory.DOCTOR_CONFLICT,
                priority=ConflictPriority.HIGH,
                description="",
                affected_objects=[],
                time_window={},
            ),
        ]
        
        summary = generate_summary(conflicts)
        
        self.assertGreater(len(summary.recommendations), 0)


class GenerateConflictReportTest(TestCase):
    """Test full report generation."""

    databases = {"default"}

    def test_generates_complete_report(self):
        """Should generate complete conflict report."""
        report = generate_conflict_report(seed=8301)
        
        self.assertIsInstance(report, ConflictReport)
        self.assertIsNotNone(report.timestamp)
        self.assertIsNotNone(report.report_id)

    def test_report_has_conflicts(self):
        """Report should contain conflicts."""
        report = generate_conflict_report(seed=8302)
        
        self.assertGreater(len(report.all_conflicts), 0)

    def test_report_has_groups(self):
        """Report should have conflict groups."""
        report = generate_conflict_report(seed=8303)
        
        self.assertGreater(len(report.grouped_by_type), 0)
        self.assertGreater(len(report.grouped_by_priority), 0)

    def test_report_has_examples(self):
        """Report should have examples."""
        report = generate_conflict_report(seed=8304)
        
        self.assertGreater(len(report.examples), 0)

    def test_report_has_summary(self):
        """Report should have summary."""
        report = generate_conflict_report(seed=8305)
        
        self.assertIsInstance(report.summary, ConflictSummary)
        self.assertGreater(report.summary.total_conflicts, 0)

    def test_report_to_dict(self):
        """to_dict() should return complete structure."""
        report = generate_conflict_report(seed=8306)
        
        d = report.to_dict()
        
        self.assertIn('timestamp', d)
        self.assertIn('all_conflicts', d)
        self.assertIn('summary', d)

    def test_report_to_json(self):
        """to_json() should return valid JSON."""
        report = generate_conflict_report(seed=8307)
        
        json_str = report.to_json()
        
        self.assertIsInstance(json_str, str)
        self.assertIn('"timestamp"', json_str)


class FormatTextReportTest(TestCase):
    """Test text report formatting."""

    databases = {"default"}

    def test_formats_report(self):
        """Should format report as text."""
        report = generate_conflict_report(seed=8401)
        text = format_text_report(report)
        
        self.assertIsInstance(text, str)
        self.assertIn("SCHEDULING-KONFLIKTBERICHT", text)
        self.assertIn("ÜBERSICHT ALLER KONFLIKTTYPEN", text)
        self.assertIn("ZUSAMMENFASSUNG", text)

    def test_includes_all_sections(self):
        """Text report should include all sections."""
        report = generate_conflict_report(seed=8402)
        text = format_text_report(report)
        
        self.assertIn("1. ÜBERSICHT ALLER KONFLIKTTYPEN", text)
        self.assertIn("2. ZUSAMMENFASSUNG", text)
        self.assertIn("3. KONFLIKTE NACH TYP", text)
        self.assertIn("4. KONFLIKTE NACH PRIORITÄT", text)
        self.assertIn("5. DETAILLIERTE KONFLIKTBESCHREIBUNGEN", text)
        self.assertIn("6. KONFLIKT-BEISPIELE", text)
        self.assertIn("7. EMPFEHLUNGEN ZUR OPTIMIERUNG", text)

    def test_includes_conflict_ids(self):
        """Text report should include conflict IDs."""
        report = generate_conflict_report(seed=8403)
        text = format_text_report(report)
        
        self.assertIn("CONF-", text)


class ConflictReportTest(TestCase):
    """Test ConflictReport data class."""

    def test_to_json_valid(self):
        """to_json() should produce valid JSON."""
        import json
        
        report = ConflictReport(
            timestamp="2025-01-01T12:00:00",
            report_id="TEST-001",
            conflict_types_overview=[],
            all_conflicts=[],
            grouped_by_type=[],
            grouped_by_priority=[],
            grouped_by_doctor=[],
            grouped_by_room=[],
            examples=[],
            summary=ConflictSummary(),
        )
        
        json_str = report.to_json()
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed['report_id'], "TEST-001")
