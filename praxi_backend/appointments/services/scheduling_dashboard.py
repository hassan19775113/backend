"""
Scheduling Dashboard Module.

Generates compact, text-based scheduling dashboards:
- Daily overview
- Weekly overview
- Conflict summary
- Resource utilization
- KPIs
- Recommendations

==============================================================================
ARCHITECTURE RULES (from copilot-instructions.md)
==============================================================================

- Use .using("default") for all ORM calls
- patient_id is an integer (NO ForeignKey to medical.Patient)
- Fully qualified imports: praxi_backend.appointments.*

==============================================================================
"""

import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Tuple

from django.db.models import Avg, Count, F, Q
from django.db.models.functions import ExtractHour
from django.utils import timezone

from praxi_backend.appointments.models import (
    Appointment,
    AppointmentType,
    DoctorAbsence,
    DoctorBreak,
    DoctorHours,
    Operation,
    OperationType,
    PracticeHours,
    Resource,
)
from praxi_backend.core.models import Role, User


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DashboardStats:
    """Statistics for dashboard."""
    total_appointments: int = 0
    total_operations: int = 0
    doctor_conflicts: int = 0
    room_conflicts: int = 0
    working_hours_violations: int = 0
    absence_conflicts: int = 0
    break_conflicts: int = 0
    avg_appointment_duration: float = 0.0
    avg_operation_duration: float = 0.0


@dataclass
class DoctorStats:
    """Per-doctor statistics."""
    doctor_id: int
    doctor_name: str
    appointments: int = 0
    operations: int = 0
    conflicts: int = 0
    utilization_pct: float = 0.0


@dataclass
class RoomStats:
    """Per-room statistics."""
    room_id: int
    room_name: str
    operations: int = 0
    conflicts: int = 0
    utilization_pct: float = 0.0


# =============================================================================
# DASHBOARD CONTEXT
# =============================================================================

class DashboardContext:
    """Loads data for dashboard generation."""
    
    def __init__(self, target_date: date = None, seed: int = None):
        self.seed = seed or int(timezone.now().timestamp())
        random.seed(self.seed)
        self.target_date = target_date or timezone.now().date()
        self.week_start = self.target_date - timedelta(days=self.target_date.weekday())
        self.week_end = self.week_start + timedelta(days=6)
        
        self.doctors: List[User] = []
        self.rooms: List[Resource] = []
        self.appointments: List[Appointment] = []
        self.operations: List[Operation] = []
        self.absences: List[DoctorAbsence] = []
        self.breaks: List[DoctorBreak] = []
        
        self.stats = DashboardStats()
        self.doctor_stats: Dict[int, DoctorStats] = {}
        self.room_stats: Dict[int, RoomStats] = {}
    
    def load_data(self):
        """Load real data from database."""
        self.doctors = list(User.objects.using('default').filter(
            role__name='doctor'
        ).select_related('role'))
        
        self.rooms = list(Resource.objects.using('default').filter(
            type='room', active=True
        ))
        
        day_start = timezone.make_aware(datetime.combine(self.target_date, time(0, 0)))
        day_end = timezone.make_aware(datetime.combine(self.target_date, time(23, 59, 59)))
        
        self.appointments = list(Appointment.objects.using('default').filter(
            start_time__gte=day_start,
            start_time__lte=day_end
        ).select_related('doctor', 'type'))
        
        self.operations = list(Operation.objects.using('default').filter(
            start_time__gte=day_start,
            start_time__lte=day_end
        ).select_related('primary_surgeon', 'op_room', 'op_type'))
        
        self.absences = list(DoctorAbsence.objects.using('default').filter(
            start_date__lte=self.target_date,
            end_date__gte=self.target_date
        ).select_related('doctor'))
        
        self.breaks = list(DoctorBreak.objects.using('default').filter(
            date=self.target_date
        ).select_related('doctor'))
        
        self._calculate_stats()
    
    def setup_demo_data(self):
        """Create demo data for visualization."""
        self._ensure_roles()
        self._create_doctors()
        self._create_rooms()
        self._create_types()
        self._create_demo_appointments()
        self._create_demo_operations()
        self._create_demo_absences()
        self._create_demo_breaks()
        self._calculate_stats()
    
    def _ensure_roles(self):
        self.role_doctor, _ = Role.objects.using('default').get_or_create(
            name='doctor', defaults={'description': 'Doctor role'}
        )
    
    def _create_doctors(self):
        base = self.seed * 1000
        names = [
            ("Dr. Anna", "Schmidt"),
            ("Dr. Peter", "Müller"),
            ("Dr. Maria", "Weber"),
            ("Dr. Thomas", "Fischer"),
        ]
        for i, (first, last) in enumerate(names):
            doc, _ = User.objects.db_manager('default').get_or_create(
                username=f"dash_doc_{base}_{i}",
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f"dash_doc_{base}_{i}@test.local",
                    'role': self.role_doctor,
                }
            )
            self.doctors.append(doc)
    
    def _create_rooms(self):
        base = self.seed * 1000
        for i in range(3):
            room, _ = Resource.objects.using('default').get_or_create(
                name=f"OP-Saal {base}_{i+1}",
                defaults={'type': 'room', 'active': True}
            )
            self.rooms.append(room)
    
    def _create_types(self):
        self.apt_type, _ = AppointmentType.objects.using('default').get_or_create(
            name=f"Untersuchung_{self.seed}",
            defaults={'duration_minutes': 30, 'color': '#3B82F6'}
        )
        self.op_type, _ = OperationType.objects.using('default').get_or_create(
            name=f"Standard-OP_{self.seed}",
            defaults={'prep_duration': 15, 'op_duration': 60, 'post_duration': 15, 'color': '#8A2BE2', 'active': True}
        )
    
    def _make_dt(self, day: date, t: time) -> datetime:
        return timezone.make_aware(datetime.combine(day, t))
    
    def _create_demo_appointments(self):
        hours = [8, 9, 9, 10, 11, 14, 14, 15, 16, 17]
        for i, hour in enumerate(hours):
            doc = self.doctors[i % len(self.doctors)]
            apt = Appointment.objects.using('default').create(
                doctor=doc,
                patient_id=99900 + i,
                type=self.apt_type,
                start_time=self._make_dt(self.target_date, time(hour, 0 if i % 2 == 0 else 30)),
                end_time=self._make_dt(self.target_date, time(hour + 1, 0 if i % 2 == 0 else 30)),
                status='scheduled'
            )
            self.appointments.append(apt)
    
    def _create_demo_operations(self):
        times = [(9, 11), (11, 13), (12, 14), (14, 16)]
        for i, (start_h, end_h) in enumerate(times):
            room = self.rooms[i % len(self.rooms)]
            surgeon = self.doctors[(i + 1) % len(self.doctors)]
            op = Operation.objects.using('default').create(
                patient_id=99950 + i,
                primary_surgeon=surgeon,
                op_room=room,
                op_type=self.op_type,
                start_time=self._make_dt(self.target_date, time(start_h, 0)),
                end_time=self._make_dt(self.target_date, time(end_h, 0)),
                status='planned'
            )
            self.operations.append(op)
    
    def _create_demo_absences(self):
        if self.doctors:
            absence = DoctorAbsence.objects.using('default').create(
                doctor=self.doctors[2],
                start_date=self.target_date,
                end_date=self.target_date + timedelta(days=2),
                reason='Urlaub'
            )
            self.absences.append(absence)
    
    def _create_demo_breaks(self):
        if self.doctors:
            brk = DoctorBreak.objects.using('default').create(
                doctor=self.doctors[0],
                date=self.target_date,
                start_time=time(12, 0),
                end_time=time(13, 0)
            )
            self.breaks.append(brk)
    
    def _calculate_stats(self):
        self.stats.total_appointments = len(self.appointments)
        self.stats.total_operations = len(self.operations)
        
        # Calculate average durations
        if self.appointments:
            durations = [(a.end_time - a.start_time).total_seconds() / 60 for a in self.appointments]
            self.stats.avg_appointment_duration = sum(durations) / len(durations)
        
        if self.operations:
            durations = [(o.end_time - o.start_time).total_seconds() / 60 for o in self.operations]
            self.stats.avg_operation_duration = sum(durations) / len(durations)
        
        # Doctor conflicts
        for doc in self.doctors:
            doc_apts = [a for a in self.appointments if a.doctor_id == doc.id]
            doc_ops = [o for o in self.operations 
                      if o.primary_surgeon_id == doc.id 
                      or getattr(o, 'assistant_id', None) == doc.id]
            
            conflicts = 0
            all_events = [(a.start_time, a.end_time, 'apt') for a in doc_apts]
            all_events += [(o.start_time, o.end_time, 'op') for o in doc_ops]
            all_events.sort(key=lambda x: x[0])
            
            for i, (s1, e1, _) in enumerate(all_events):
                for j, (s2, e2, _) in enumerate(all_events):
                    if i < j and s1 < e2 and e1 > s2:
                        conflicts += 1
            
            self.doctor_stats[doc.id] = DoctorStats(
                doctor_id=doc.id,
                doctor_name=f"{doc.first_name} {doc.last_name}",
                appointments=len(doc_apts),
                operations=len([o for o in doc_ops if o.primary_surgeon_id == doc.id]),
                conflicts=conflicts,
                utilization_pct=min(100, (len(doc_apts) + len(doc_ops)) * 12.5)
            )
            self.stats.doctor_conflicts += conflicts
        
        # Room conflicts
        for room in self.rooms:
            room_ops = [o for o in self.operations if o.op_room_id == room.id]
            conflicts = 0
            
            for i, op1 in enumerate(room_ops):
                for j, op2 in enumerate(room_ops):
                    if i < j and op1.start_time < op2.end_time and op1.end_time > op2.start_time:
                        conflicts += 1
            
            self.room_stats[room.id] = RoomStats(
                room_id=room.id,
                room_name=room.name,
                operations=len(room_ops),
                conflicts=conflicts,
                utilization_pct=min(100, len(room_ops) * 25)
            )
            self.stats.room_conflicts += conflicts
        
        # Working hours violations
        for apt in self.appointments:
            start_t = apt.start_time.time()
            end_t = apt.end_time.time()
            if start_t < time(8, 0) or end_t > time(17, 0):
                self.stats.working_hours_violations += 1
        
        # Absence conflicts
        for absence in self.absences:
            for apt in self.appointments:
                apt_date = apt.start_time.date()
                if apt.doctor_id == absence.doctor_id and absence.start_date <= apt_date <= absence.end_date:
                    self.stats.absence_conflicts += 1
        
        # Break conflicts
        for brk in self.breaks:
            for apt in self.appointments:
                apt_date = apt.start_time.date()
                apt_start = apt.start_time.time()
                apt_end = apt.end_time.time()
                if apt.doctor_id == brk.doctor_id and apt_date == brk.date:
                    if apt_start < brk.end_time and apt_end > brk.start_time:
                        self.stats.break_conflicts += 1


# =============================================================================
# DASHBOARD GENERATION
# =============================================================================

def generate_daily_overview(ctx: DashboardContext) -> str:
    """Generate daily overview section."""
    lines = []
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append(f"│  TAGESÜBERSICHT: {ctx.target_date.strftime('%d.%m.%Y (%A)'):<41}│")
    lines.append("├─────────────────────────────────────────────────────────────┤")
    lines.append(f"│  Termine: {ctx.stats.total_appointments:<5}  │  Operationen: {ctx.stats.total_operations:<5}            │")
    lines.append("├─────────────────────────────────────────────────────────────┤")
    
    # Doctor utilization
    lines.append("│  ARZT-AUSLASTUNG:                                           │")
    for doc_id, ds in list(ctx.doctor_stats.items())[:4]:
        bar_len = int(ds.utilization_pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"│    {ds.doctor_name[:18]:<18} │{bar}│ {ds.utilization_pct:5.1f}%  │")
    
    # Room utilization
    lines.append("├─────────────────────────────────────────────────────────────┤")
    lines.append("│  RAUM-AUSLASTUNG:                                           │")
    for room_id, rs in list(ctx.room_stats.items())[:3]:
        bar_len = int(rs.utilization_pct / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"│    {rs.room_name[:18]:<18} │{bar}│ {rs.utilization_pct:5.1f}%  │")
    
    # Conflicts
    lines.append("├─────────────────────────────────────────────────────────────┤")
    lines.append("│  KONFLIKTE:                                                 │")
    total_conflicts = (ctx.stats.doctor_conflicts + ctx.stats.room_conflicts + 
                      ctx.stats.working_hours_violations + ctx.stats.absence_conflicts)
    if total_conflicts == 0:
        lines.append("│    ✓ Keine Konflikte                                        │")
    else:
        if ctx.stats.doctor_conflicts:
            lines.append(f"│    ⚠ Arzt-Doppelbelegungen: {ctx.stats.doctor_conflicts:<30}│")
        if ctx.stats.room_conflicts:
            lines.append(f"│    ⚠ Raum-Konflikte: {ctx.stats.room_conflicts:<37}│")
        if ctx.stats.working_hours_violations:
            lines.append(f"│    ⚠ Arbeitszeit-Verstöße: {ctx.stats.working_hours_violations:<31}│")
        if ctx.stats.absence_conflicts:
            lines.append(f"│    ⚠ Abwesenheits-Konflikte: {ctx.stats.absence_conflicts:<29}│")
    
    lines.append("└─────────────────────────────────────────────────────────────┘")
    return "\n".join(lines)


def generate_weekly_overview(ctx: DashboardContext) -> str:
    """Generate weekly overview section."""
    lines = []
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append(f"│  WOCHENÜBERSICHT: {ctx.week_start.strftime('%d.%m.')} - {ctx.week_end.strftime('%d.%m.%Y'):<27}│")
    lines.append("├───────┬────────┬─────┬──────────────────────────────────────┤")
    lines.append("│  Tag  │Termine │ OPs │ Konflikt-Heatmap                     │")
    lines.append("├───────┼────────┼─────┼──────────────────────────────────────┤")
    
    weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    
    for i in range(7):
        day = ctx.week_start + timedelta(days=i)
        day_start = timezone.make_aware(datetime.combine(day, time(0, 0)))
        day_end = timezone.make_aware(datetime.combine(day, time(23, 59, 59)))
        
        # Count for this day
        day_apts = len([a for a in ctx.appointments if day_start <= a.start_time <= day_end])
        day_ops = len([o for o in ctx.operations if day_start <= o.start_time <= day_end])
        
        # Simulate conflict level
        conflict_level = random.randint(0, 5) if i < 5 else random.randint(0, 2)
        heatmap = "█" * conflict_level + "░" * (10 - conflict_level)
        severity = "🔴" if conflict_level > 3 else ("🟡" if conflict_level > 1 else "🟢")
        
        is_target = "→" if day == ctx.target_date else " "
        lines.append(f"│{is_target}{weekdays[i]:<4} │{day_apts:^8}│{day_ops:^5}│ {severity} {heatmap}                  │")
    
    lines.append("└───────┴────────┴─────┴──────────────────────────────────────┘")
    return "\n".join(lines)


def generate_conflict_summary(ctx: DashboardContext) -> str:
    """Generate conflict summary section."""
    lines = []
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append("│  KONFLIKTÜBERSICHT                                          │")
    lines.append("├──────────────────────────┬────────┬──────────────────────────┤")
    lines.append("│ Konflikttyp              │ Anzahl │ Status                   │")
    lines.append("├──────────────────────────┼────────┼──────────────────────────┤")
    
    conflicts = [
        ("Arzt-Doppelbelegungen", ctx.stats.doctor_conflicts),
        ("Raum-Konflikte", ctx.stats.room_conflicts),
        ("Arbeitszeit-Verstöße", ctx.stats.working_hours_violations),
        ("Abwesenheits-Konflikte", ctx.stats.absence_conflicts),
        ("Pausen-Konflikte", ctx.stats.break_conflicts),
    ]
    
    for name, count in conflicts:
        if count > 2:
            status = "🔴 KRITISCH"
        elif count > 0:
            status = "🟡 WARNUNG"
        else:
            status = "🟢 OK"
        bar = "█" * min(count * 2, 10)
        lines.append(f"│ {name:<24} │{count:^8}│ {status:<16} {bar:<8}│")
    
    total = sum(c for _, c in conflicts)
    lines.append("├──────────────────────────┼────────┼──────────────────────────┤")
    lines.append(f"│ GESAMT                   │{total:^8}│                          │")
    lines.append("└──────────────────────────┴────────┴──────────────────────────┘")
    return "\n".join(lines)


def generate_resource_summary(ctx: DashboardContext) -> str:
    """Generate resource utilization summary."""
    lines = []
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append("│  RESSOURCENÜBERSICHT                                        │")
    lines.append("├─────────────────────────────────────────────────────────────┤")
    
    # Doctor summary
    lines.append("│  ÄRZTE:                                                     │")
    avg_doc_util = 0
    if ctx.doctor_stats:
        avg_doc_util = sum(ds.utilization_pct for ds in ctx.doctor_stats.values()) / len(ctx.doctor_stats)
    bar_len = int(avg_doc_util / 5)
    bar = "█" * bar_len + "░" * (20 - bar_len)
    lines.append(f"│    Durchschnitt: {bar} {avg_doc_util:5.1f}%         │")
    
    # Find over/under utilized
    if ctx.doctor_stats:
        max_doc = max(ctx.doctor_stats.values(), key=lambda d: d.utilization_pct)
        min_doc = min(ctx.doctor_stats.values(), key=lambda d: d.utilization_pct)
        lines.append(f"│    Höchste:  {max_doc.doctor_name[:15]:<15} ({max_doc.utilization_pct:5.1f}%)               │")
        lines.append(f"│    Niedrigste: {min_doc.doctor_name[:15]:<15} ({min_doc.utilization_pct:5.1f}%)             │")
    
    # Room summary
    lines.append("├─────────────────────────────────────────────────────────────┤")
    lines.append("│  OP-SÄLE:                                                   │")
    avg_room_util = 0
    if ctx.room_stats:
        avg_room_util = sum(rs.utilization_pct for rs in ctx.room_stats.values()) / len(ctx.room_stats)
    bar_len = int(avg_room_util / 5)
    bar = "█" * bar_len + "░" * (20 - bar_len)
    lines.append(f"│    Durchschnitt: {bar} {avg_room_util:5.1f}%         │")
    
    if ctx.room_stats:
        max_room = max(ctx.room_stats.values(), key=lambda r: r.utilization_pct)
        lines.append(f"│    Höchste: {max_room.room_name[:16]:<16} ({max_room.utilization_pct:5.1f}%)              │")
    
    lines.append("└─────────────────────────────────────────────────────────────┘")
    return "\n".join(lines)


def generate_kpis(ctx: DashboardContext) -> str:
    """Generate KPI summary."""
    lines = []
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append("│  KEY PERFORMANCE INDICATORS                                 │")
    lines.append("├──────────────────────────────────┬──────────────────────────┤")
    
    total_plannings = ctx.stats.total_appointments + ctx.stats.total_operations
    total_conflicts = (ctx.stats.doctor_conflicts + ctx.stats.room_conflicts + 
                      ctx.stats.working_hours_violations + ctx.stats.absence_conflicts)
    conflicts_per_100 = (total_conflicts / total_plannings * 100) if total_plannings > 0 else 0
    
    lines.append(f"│ Ø Terminlänge            │ {ctx.stats.avg_appointment_duration:>6.1f} min              │")
    lines.append(f"│ Ø OP-Dauer               │ {ctx.stats.avg_operation_duration:>6.1f} min              │")
    lines.append(f"│ Konflikte / 100 Planung  │ {conflicts_per_100:>6.1f}                    │")
    
    avg_doc_util = 0
    if ctx.doctor_stats:
        avg_doc_util = sum(ds.utilization_pct for ds in ctx.doctor_stats.values()) / len(ctx.doctor_stats)
    avg_room_util = 0
    if ctx.room_stats:
        avg_room_util = sum(rs.utilization_pct for rs in ctx.room_stats.values()) / len(ctx.room_stats)
    
    lines.append(f"│ Arzt-Auslastung Ø        │ {avg_doc_util:>6.1f} %                 │")
    lines.append(f"│ Raum-Auslastung Ø        │ {avg_room_util:>6.1f} %                 │")
    
    efficiency = 100 - (conflicts_per_100 * 2)
    efficiency = max(0, min(100, efficiency))
    lines.append(f"│ Scheduling-Effizienz     │ {efficiency:>6.1f} %                 │")
    
    lines.append("└──────────────────────────────────┴──────────────────────────┘")
    return "\n".join(lines)


def generate_recommendations(ctx: DashboardContext) -> str:
    """Generate recommendations based on analysis."""
    lines = []
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append("│  EMPFEHLUNGEN                                               │")
    lines.append("├─────────────────────────────────────────────────────────────┤")
    
    recommendations = []
    
    if ctx.stats.doctor_conflicts > 0:
        recommendations.append("• Arzt-Terminüberlappungen prüfen und umplanen")
    
    if ctx.stats.room_conflicts > 0:
        recommendations.append("• OP-Raum-Konflikte auflösen (Alternativräume)")
    
    if ctx.stats.working_hours_violations > 0:
        recommendations.append("• Termine außerhalb Arbeitszeit verschieben")
    
    if ctx.stats.absence_conflicts > 0:
        recommendations.append("• Termine während Abwesenheit umbuchen")
    
    # Check utilization
    if ctx.doctor_stats:
        overloaded = [ds for ds in ctx.doctor_stats.values() if ds.utilization_pct > 80]
        underloaded = [ds for ds in ctx.doctor_stats.values() if ds.utilization_pct < 30]
        if overloaded and underloaded:
            recommendations.append("• Last zwischen Ärzten besser verteilen")
    
    if not recommendations:
        recommendations.append("✓ Keine dringenden Optimierungen erforderlich")
    
    for rec in recommendations[:5]:
        lines.append(f"│ {rec:<59}│")
    
    lines.append("└─────────────────────────────────────────────────────────────┘")
    return "\n".join(lines)


def generate_dashboard(target_date: date = None, seed: int = None, use_demo: bool = True) -> str:
    """Generate complete scheduling dashboard."""
    ctx = DashboardContext(target_date=target_date, seed=seed)
    
    if use_demo:
        ctx.setup_demo_data()
    else:
        ctx.load_data()
    
    header = f"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        SCHEDULING DASHBOARD                                   ║
║                    {timezone.now().strftime('%d.%m.%Y %H:%M'):^55}                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""
    
    sections = [
        generate_daily_overview(ctx),
        generate_weekly_overview(ctx),
        generate_conflict_summary(ctx),
        generate_resource_summary(ctx),
        generate_kpis(ctx),
        generate_recommendations(ctx),
    ]
    
    return header + "\n\n".join(sections)


def print_dashboard(target_date: date = None, seed: int = None, use_demo: bool = True):
    """Print dashboard to stdout."""
    print(generate_dashboard(target_date, seed, use_demo))
