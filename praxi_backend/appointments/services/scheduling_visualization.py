"""
Scheduling Conflict Visualization Module.

Generates text-based visualizations of scheduling conflicts:
- Timeline diagrams
- Conflict tables
- Heatmaps (ASCII)
- Absence visualizations
- Working hours visualizations
- Edge case diagrams

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

from django.utils import timezone

from praxi_backend.appointments.models import (
    Appointment,
    AppointmentResource,
    AppointmentType,
    DoctorAbsence,
    DoctorBreak,
    DoctorHours,
    Operation,
    OperationDevice,
    OperationType,
    PracticeHours,
    Resource,
)
from praxi_backend.core.models import Role, User


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class TimeSlot:
    """A time slot with start and end times."""
    start: time
    end: time
    label: str
    slot_type: str = "appointment"
    entity_id: Optional[int] = None
    conflict: bool = False
    conflict_with: Optional[str] = None


@dataclass
class ConflictVisualization:
    """Complete visualization output."""
    title: str
    sections: List[str] = field(default_factory=list)
    
    def add_section(self, title: str, content: str):
        self.sections.append(f"\n{'=' * 80}\n{title}\n{'=' * 80}\n\n{content}")
    
    def render(self) -> str:
        header = f"""
╔{'═' * 78}╗
║{self.title:^78}║
╚{'═' * 78}╝
"""
        return header + "\n".join(self.sections)


# =============================================================================
# VISUALIZATION CONTEXT
# =============================================================================

class VisualizationContext:
    """Sets up test data for visualization."""
    
    def __init__(self, seed: int = None):
        self.seed = seed or int(timezone.now().timestamp())
        random.seed(self.seed)
        self.doctors: List[User] = []
        self.rooms: List[Resource] = []
        self.devices: List[Resource] = []
        self.appointments: List[Appointment] = []
        self.operations: List[Operation] = []
        self.absences: List[DoctorAbsence] = []
        self.breaks: List[DoctorBreak] = []
        self.today = timezone.now().date()
    
    def setup(self):
        """Create test data for visualization."""
        self._create_roles()
        self._create_doctors()
        self._create_resources()
        self._create_appointment_types()
        self._create_operation_types()
        self._create_practice_hours()
        self._create_doctor_hours()
        self._create_conflicts()
    
    def _create_roles(self):
        self.role_doctor, _ = Role.objects.using('default').get_or_create(
            name='doctor',
            defaults={'description': 'Doctor role'}
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
                username=f"viz_doc_{base}_{i}",
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f"viz_doc_{base}_{i}@test.local",
                    'role': self.role_doctor,
                }
            )
            self.doctors.append(doc)
    
    def _create_resources(self):
        base = self.seed * 1000
        for i in range(3):
            room, _ = Resource.objects.using('default').get_or_create(
                name=f"OP-Saal {base}_{i+1}",
                defaults={'type': 'room', 'active': True}
            )
            self.rooms.append(room)
        
        for i in range(2):
            device, _ = Resource.objects.using('default').get_or_create(
                name=f"Gerät {base}_{i+1}",
                defaults={'type': 'device', 'active': True}
            )
            self.devices.append(device)
    
    def _create_appointment_types(self):
        self.apt_type, _ = AppointmentType.objects.using('default').get_or_create(
            name=f"Untersuchung_{self.seed}",
            defaults={'duration_minutes': 30, 'color': '#3B82F6'}
        )
    
    def _create_operation_types(self):
        self.op_type, _ = OperationType.objects.using('default').get_or_create(
            name=f"Standard-OP_{self.seed}",
            defaults={
                'prep_duration': 15,
                'op_duration': 60,
                'post_duration': 15,
                'color': '#8A2BE2',
                'active': True
            }
        )
    
    def _create_practice_hours(self):
        for weekday in range(5):
            PracticeHours.objects.using('default').get_or_create(
                weekday=weekday,
                start_time=time(8, 0),
                end_time=time(17, 0),
                defaults={'active': True}
            )
    
    def _create_doctor_hours(self):
        for doc in self.doctors:
            for weekday in range(5):
                DoctorHours.objects.using('default').get_or_create(
                    doctor=doc,
                    weekday=weekday,
                    defaults={
                        'start_time': time(8, 0),
                        'end_time': time(17, 0),
                        'active': True
                    }
                )
    
    def _make_datetime(self, day: date, t: time) -> datetime:
        """Create timezone-aware datetime."""
        return timezone.make_aware(datetime.combine(day, t))
    
    def _create_conflicts(self):
        """Create various conflict scenarios."""
        doc = self.doctors[0]
        room = self.rooms[0]
        
        # Doctor conflict: Two appointments same time
        apt1 = Appointment.objects.using('default').create(
            doctor=doc,
            patient_id=99901,
            type=self.apt_type,
            start_time=self._make_datetime(self.today, time(9, 0)),
            end_time=self._make_datetime(self.today, time(10, 0)),
            status='scheduled'
        )
        self.appointments.append(apt1)
        
        apt2 = Appointment.objects.using('default').create(
            doctor=doc,
            patient_id=99902,
            type=self.apt_type,
            start_time=self._make_datetime(self.today, time(9, 30)),
            end_time=self._make_datetime(self.today, time(10, 30)),
            status='scheduled'
        )
        self.appointments.append(apt2)
        
        # Room conflict: Two operations same room
        op1 = Operation.objects.using('default').create(
            patient_id=99903,
            primary_surgeon=self.doctors[1],
            op_room=room,
            op_type=self.op_type,
            start_time=self._make_datetime(self.today, time(11, 0)),
            end_time=self._make_datetime(self.today, time(12, 30)),
            status='planned'
        )
        self.operations.append(op1)
        
        op2 = Operation.objects.using('default').create(
            patient_id=99904,
            primary_surgeon=self.doctors[2],
            op_room=room,
            op_type=self.op_type,
            start_time=self._make_datetime(self.today, time(12, 0)),
            end_time=self._make_datetime(self.today, time(13, 30)),
            status='planned'
        )
        self.operations.append(op2)
        
        # Working hours violation
        apt3 = Appointment.objects.using('default').create(
            doctor=self.doctors[1],
            patient_id=99905,
            type=self.apt_type,
            start_time=self._make_datetime(self.today, time(17, 30)),
            end_time=self._make_datetime(self.today, time(18, 30)),
            status='scheduled'
        )
        self.appointments.append(apt3)
        
        # Doctor absence
        absence = DoctorAbsence.objects.using('default').create(
            doctor=self.doctors[2],
            start_date=self.today,
            end_date=self.today + timedelta(days=2),
            reason='Urlaub'
        )
        self.absences.append(absence)
        
        # Appointment during absence
        apt4 = Appointment.objects.using('default').create(
            doctor=self.doctors[2],
            patient_id=99906,
            type=self.apt_type,
            start_time=self._make_datetime(self.today, time(14, 0)),
            end_time=self._make_datetime(self.today, time(15, 0)),
            status='scheduled'
        )
        self.appointments.append(apt4)
        
        # Doctor break conflict
        break1 = DoctorBreak.objects.using('default').create(
            doctor=self.doctors[3],
            date=self.today,
            start_time=time(12, 0),
            end_time=time(13, 0)
        )
        self.breaks.append(break1)
        
        apt5 = Appointment.objects.using('default').create(
            doctor=self.doctors[3],
            patient_id=99907,
            type=self.apt_type,
            start_time=self._make_datetime(self.today, time(12, 30)),
            end_time=self._make_datetime(self.today, time(13, 30)),
            status='scheduled'
        )
        self.appointments.append(apt5)
        
        # More appointments for heatmap
        for hour in [8, 10, 14, 15, 16]:
            apt = Appointment.objects.using('default').create(
                doctor=random.choice(self.doctors),
                patient_id=99900 + hour,
                type=self.apt_type,
                start_time=self._make_datetime(self.today, time(hour, 0)),
                end_time=self._make_datetime(self.today, time(hour + 1, 0)),
                status='scheduled'
            )
            self.appointments.append(apt)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_time_from_datetime(dt: datetime) -> time:
    """Extract time from datetime."""
    return dt.time() if dt else time(0, 0)


def get_date_from_datetime(dt: datetime) -> date:
    """Extract date from datetime."""
    return dt.date() if dt else date.today()


# =============================================================================
# TIMELINE VISUALIZATION
# =============================================================================

def render_timeline(slots: List[TimeSlot], title: str = "", width: int = 60) -> str:
    """Render a timeline with slots."""
    if not slots:
        return f"{title}\n  (keine Einträge)"
    
    lines = []
    if title:
        lines.append(f"  {title}")
        lines.append("  " + "─" * width)
    
    lines.append(f"  08:00{'─' * 10}10:00{'─' * 10}12:00{'─' * 10}14:00{'─' * 10}16:00{'─' * 10}18:00")
    lines.append("  │" + " " * 58 + "│")
    
    for slot in sorted(slots, key=lambda s: s.start):
        start_min = slot.start.hour * 60 + slot.start.minute
        end_min = slot.end.hour * 60 + slot.end.minute
        start_pos = max(0, int((start_min - 480) / 10))
        end_pos = min(60, int((end_min - 480) / 10))
        length = max(1, end_pos - start_pos)
        
        marker = "█" if slot.conflict else "░"
        bar = marker * length
        prefix = " " * start_pos
        suffix = f"  ⚠ KONFLIKT: {slot.conflict_with}" if slot.conflict else ""
        time_label = f"{slot.start.strftime('%H:%M')}-{slot.end.strftime('%H:%M')}"
        lines.append(f"  │{prefix}{bar}{' ' * (58 - start_pos - length)}│ {slot.label[:15]:<15} {time_label} {suffix}")
    
    lines.append("  │" + " " * 58 + "│")
    lines.append("  " + "─" * 62)
    return "\n".join(lines)


def visualize_doctor_conflicts(ctx: VisualizationContext) -> str:
    """Visualize doctor conflicts as timelines."""
    output = []
    
    for doc in ctx.doctors:
        appointments = [a for a in ctx.appointments if a.doctor_id == doc.id]
        operations = [o for o in ctx.operations 
                     if o.primary_surgeon_id == doc.id 
                     or o.assistant_id == doc.id 
                     or o.anesthesist_id == doc.id]
        
        if not appointments and not operations:
            continue
        
        slots = []
        for apt in appointments:
            slots.append(TimeSlot(
                start=get_time_from_datetime(apt.start_time),
                end=get_time_from_datetime(apt.end_time),
                label=f"Termin #{apt.id}",
                slot_type="appointment",
                entity_id=apt.id
            ))
        
        for op in operations:
            slots.append(TimeSlot(
                start=get_time_from_datetime(op.start_time),
                end=get_time_from_datetime(op.end_time),
                label=f"OP #{op.id}",
                slot_type="operation",
                entity_id=op.id
            ))
        
        sorted_slots = sorted(slots, key=lambda s: s.start)
        for i, slot in enumerate(sorted_slots):
            for j, other in enumerate(sorted_slots):
                if i != j and slot.start < other.end and slot.end > other.start:
                    slot.conflict = True
                    slot.conflict_with = other.label
        
        output.append(render_timeline(slots, f"Arzt: {doc.first_name} {doc.last_name} (ID: {doc.id})"))
    
    return "\n\n".join(output) if output else "(keine Arzt-Konflikte)"


def visualize_room_conflicts(ctx: VisualizationContext) -> str:
    """Visualize room conflicts as timelines."""
    output = []
    
    for room in ctx.rooms:
        operations = [o for o in ctx.operations if o.op_room_id == room.id]
        if not operations:
            continue
        
        slots = []
        for op in operations:
            slots.append(TimeSlot(
                start=get_time_from_datetime(op.start_time),
                end=get_time_from_datetime(op.end_time),
                label=f"OP #{op.id}",
                slot_type="operation",
                entity_id=op.id
            ))
        
        sorted_slots = sorted(slots, key=lambda s: s.start)
        for i, slot in enumerate(sorted_slots):
            for j, other in enumerate(sorted_slots):
                if i != j and slot.start < other.end and slot.end > other.start:
                    slot.conflict = True
                    slot.conflict_with = other.label
        
        output.append(render_timeline(slots, f"Raum: {room.name}"))
    
    return "\n\n".join(output) if output else "(keine Raum-Konflikte)"


# =============================================================================
# TABLE VISUALIZATION
# =============================================================================

def create_conflict_table(ctx: VisualizationContext) -> str:
    """Create a table of all conflicts."""
    conflicts = []
    
    for doc in ctx.doctors:
        appointments = [a for a in ctx.appointments if a.doctor_id == doc.id]
        sorted_apts = sorted(appointments, key=lambda a: a.start_time)
        
        for i, apt in enumerate(sorted_apts):
            for j, other in enumerate(sorted_apts):
                apt_start = get_time_from_datetime(apt.start_time)
                apt_end = get_time_from_datetime(apt.end_time)
                other_start = get_time_from_datetime(other.start_time)
                other_end = get_time_from_datetime(other.end_time)
                
                if i < j and apt_start < other_end and apt_end > other_start:
                    conflicts.append({
                        'type': 'doctor_conflict',
                        'doctor': f"{doc.first_name} {doc.last_name}",
                        'room': '-',
                        'start': apt_start,
                        'end': apt_end,
                        'severity': 'HIGH',
                        'details': f"Termin #{apt.id} vs #{other.id}"
                    })
    
    for room in ctx.rooms:
        operations = [o for o in ctx.operations if o.op_room_id == room.id]
        sorted_ops = sorted(operations, key=lambda o: o.start_time)
        
        for i, op in enumerate(sorted_ops):
            for j, other in enumerate(sorted_ops):
                op_start = get_time_from_datetime(op.start_time)
                op_end = get_time_from_datetime(op.end_time)
                other_start = get_time_from_datetime(other.start_time)
                other_end = get_time_from_datetime(other.end_time)
                
                if i < j and op_start < other_end and op_end > other_start:
                    conflicts.append({
                        'type': 'room_conflict',
                        'doctor': '-',
                        'room': room.name,
                        'start': op_start,
                        'end': op_end,
                        'severity': 'HIGH',
                        'details': f"OP #{op.id} vs #{other.id}"
                    })
    
    for apt in ctx.appointments:
        apt_start = get_time_from_datetime(apt.start_time)
        apt_end = get_time_from_datetime(apt.end_time)
        if apt_start < time(8, 0) or apt_end > time(17, 0):
            conflicts.append({
                'type': 'working_hours',
                'doctor': f"{apt.doctor.first_name} {apt.doctor.last_name}",
                'room': '-',
                'start': apt_start,
                'end': apt_end,
                'severity': 'MEDIUM',
                'details': f"Termin #{apt.id} außerhalb"
            })
    
    for absence in ctx.absences:
        for apt in ctx.appointments:
            apt_date = get_date_from_datetime(apt.start_time)
            if apt.doctor_id == absence.doctor_id and absence.start_date <= apt_date <= absence.end_date:
                conflicts.append({
                    'type': 'doctor_absent',
                    'doctor': f"{apt.doctor.first_name} {apt.doctor.last_name}",
                    'room': '-',
                    'start': get_time_from_datetime(apt.start_time),
                    'end': get_time_from_datetime(apt.end_time),
                    'severity': 'HIGH',
                    'details': f"Termin #{apt.id} Abwesenheit"
                })
    
    for brk in ctx.breaks:
        for apt in ctx.appointments:
            apt_date = get_date_from_datetime(apt.start_time)
            apt_start = get_time_from_datetime(apt.start_time)
            apt_end = get_time_from_datetime(apt.end_time)
            if apt.doctor_id == brk.doctor_id and apt_date == brk.date:
                if apt_start < brk.end_time and apt_end > brk.start_time:
                    conflicts.append({
                        'type': 'doctor_break',
                        'doctor': f"{apt.doctor.first_name} {apt.doctor.last_name}",
                        'room': '-',
                        'start': apt_start,
                        'end': apt_end,
                        'severity': 'MEDIUM',
                        'details': f"Termin #{apt.id} Pause"
                    })
    
    lines = []
    lines.append("┌" + "─" * 18 + "┬" + "─" * 18 + "┬" + "─" * 15 + "┬" + "─" * 7 + "┬" + "─" * 7 + "┬" + "─" * 8 + "┬" + "─" * 25 + "┐")
    lines.append("│{:^18}│{:^18}│{:^15}│{:^7}│{:^7}│{:^8}│{:^25}│".format("Typ", "Arzt", "Raum", "Start", "Ende", "Schwere", "Details"))
    lines.append("├" + "─" * 18 + "┼" + "─" * 18 + "┼" + "─" * 15 + "┼" + "─" * 7 + "┼" + "─" * 7 + "┼" + "─" * 8 + "┼" + "─" * 25 + "┤")
    
    for c in conflicts:
        lines.append("│{:<18}│{:<18}│{:<15}│{:^7}│{:^7}│{:^8}│{:<25}│".format(
            c['type'][:18], c['doctor'][:18], str(c['room'])[:15],
            c['start'].strftime('%H:%M'), c['end'].strftime('%H:%M'),
            c['severity'], c['details'][:25]
        ))
    
    lines.append("└" + "─" * 18 + "┴" + "─" * 18 + "┴" + "─" * 15 + "┴" + "─" * 7 + "┴" + "─" * 7 + "┴" + "─" * 8 + "┴" + "─" * 25 + "┘")
    
    if not conflicts:
        return "(keine Konflikte gefunden)"
    lines.insert(0, f"Gesamt: {len(conflicts)} Konflikte\n")
    return "\n".join(lines)


def create_grouped_tables(ctx: VisualizationContext) -> str:
    """Create tables grouped by type and severity."""
    conflicts = []
    
    for doc in ctx.doctors:
        appointments = [a for a in ctx.appointments if a.doctor_id == doc.id]
        for i, apt in enumerate(appointments):
            for j, other in enumerate(appointments):
                if i < j:
                    apt_start = get_time_from_datetime(apt.start_time)
                    apt_end = get_time_from_datetime(apt.end_time)
                    other_start = get_time_from_datetime(other.start_time)
                    other_end = get_time_from_datetime(other.end_time)
                    if apt_start < other_end and apt_end > other_start:
                        conflicts.append({'type': 'doctor_conflict', 'severity': 'HIGH'})
    
    for room in ctx.rooms:
        operations = [o for o in ctx.operations if o.op_room_id == room.id]
        for i, op in enumerate(operations):
            for j, other in enumerate(operations):
                if i < j:
                    op_start = get_time_from_datetime(op.start_time)
                    op_end = get_time_from_datetime(op.end_time)
                    other_start = get_time_from_datetime(other.start_time)
                    other_end = get_time_from_datetime(other.end_time)
                    if op_start < other_end and op_end > other_start:
                        conflicts.append({'type': 'room_conflict', 'severity': 'HIGH'})
    
    for apt in ctx.appointments:
        apt_start = get_time_from_datetime(apt.start_time)
        apt_end = get_time_from_datetime(apt.end_time)
        if apt_start < time(8, 0) or apt_end > time(17, 0):
            conflicts.append({'type': 'working_hours', 'severity': 'MEDIUM'})
    
    for absence in ctx.absences:
        for apt in ctx.appointments:
            apt_date = get_date_from_datetime(apt.start_time)
            if apt.doctor_id == absence.doctor_id and absence.start_date <= apt_date <= absence.end_date:
                conflicts.append({'type': 'doctor_absent', 'severity': 'HIGH'})
    
    for brk in ctx.breaks:
        for apt in ctx.appointments:
            apt_date = get_date_from_datetime(apt.start_time)
            apt_start = get_time_from_datetime(apt.start_time)
            apt_end = get_time_from_datetime(apt.end_time)
            if apt.doctor_id == brk.doctor_id and apt_date == brk.date:
                if apt_start < brk.end_time and apt_end > brk.start_time:
                    conflicts.append({'type': 'doctor_break', 'severity': 'MEDIUM'})
    
    output = []
    by_type = defaultdict(int)
    for c in conflicts:
        by_type[c['type']] += 1
    
    output.append("Nach Konflikttyp:")
    output.append("┌" + "─" * 22 + "┬" + "─" * 8 + "┬" + "─" * 30 + "┐")
    output.append("│{:^22}│{:^8}│{:^30}│".format("Typ", "Anzahl", "Balken"))
    output.append("├" + "─" * 22 + "┼" + "─" * 8 + "┼" + "─" * 30 + "┤")
    for typ, count in sorted(by_type.items(), key=lambda x: -x[1]):
        bar = "█" * min(count * 5, 30)
        output.append("│{:<22}│{:^8}│{:<30}│".format(typ, count, bar))
    output.append("└" + "─" * 22 + "┴" + "─" * 8 + "┴" + "─" * 30 + "┘")
    
    by_severity = defaultdict(int)
    for c in conflicts:
        by_severity[c['severity']] += 1
    
    output.append("\nNach Schweregrad:")
    output.append("┌" + "─" * 15 + "┬" + "─" * 8 + "┬" + "─" * 30 + "┐")
    for sev in ['HIGH', 'MEDIUM', 'LOW']:
        if sev in by_severity:
            bar = "█" * min(by_severity[sev] * 5, 30)
            marker = "🔴" if sev == "HIGH" else ("🟡" if sev == "MEDIUM" else "🟢")
            output.append("│{:^15}│{:^8}│{:<30}│".format(f"{marker} {sev}", by_severity[sev], bar))
    output.append("└" + "─" * 15 + "┴" + "─" * 8 + "┴" + "─" * 30 + "┘")
    
    return "\n".join(output)


# =============================================================================
# HEATMAP VISUALIZATION
# =============================================================================

def create_hourly_heatmap(ctx: VisualizationContext) -> str:
    """Create an ASCII heatmap of conflicts by hour."""
    hour_counts = defaultdict(lambda: {'appointments': 0, 'operations': 0, 'conflicts': 0})
    
    for apt in ctx.appointments:
        start_hour = get_time_from_datetime(apt.start_time).hour
        end_hour = get_time_from_datetime(apt.end_time).hour
        for h in range(start_hour, min(end_hour + 1, 24)):
            hour_counts[h]['appointments'] += 1
    
    for op in ctx.operations:
        start_hour = get_time_from_datetime(op.start_time).hour
        end_hour = get_time_from_datetime(op.end_time).hour
        for h in range(start_hour, min(end_hour + 1, 24)):
            hour_counts[h]['operations'] += 1
    
    for doc in ctx.doctors:
        appointments = [a for a in ctx.appointments if a.doctor_id == doc.id]
        for i, apt in enumerate(appointments):
            for j, other in enumerate(appointments):
                if i < j:
                    apt_start = get_time_from_datetime(apt.start_time)
                    apt_end = get_time_from_datetime(apt.end_time)
                    other_start = get_time_from_datetime(other.start_time)
                    other_end = get_time_from_datetime(other.end_time)
                    if apt_start < other_end and apt_end > other_start:
                        for h in range(max(apt_start.hour, other_start.hour), min(apt_end.hour, other_end.hour) + 1):
                            hour_counts[h]['conflicts'] += 1
    
    lines = []
    lines.append("Stündliche Auslastung und Konflikte")
    lines.append("")
    lines.append("Stunde │ Termine │ OPs │ Konflikte │ Heatmap")
    lines.append("───────┼─────────┼─────┼───────────┼" + "─" * 40)
    
    for hour in range(6, 22):
        counts = hour_counts[hour]
        total = counts['appointments'] + counts['operations']
        conf = counts['conflicts']
        bar_total = "░" * min(total, 15)
        bar_conflict = "█" * min(conf * 5, 15)
        
        if conf > 0:
            intensity = "🔴" if conf > 2 else "🟡"
        elif total > 3:
            intensity = "🟢"
        else:
            intensity = "⚪"
        
        lines.append("{:02d}:00  │{:^9}│{:^5}│{:^11}│ {} {}{}".format(
            hour, counts['appointments'], counts['operations'], conf, intensity, bar_total, bar_conflict
        ))
    
    lines.append("───────┴─────────┴─────┴───────────┴" + "─" * 40)
    lines.append("Legende: ░ = Buchungen  █ = Konflikte  🔴 = Kritisch  🟡 = Warnung")
    return "\n".join(lines)


def create_doctor_heatmap(ctx: VisualizationContext) -> str:
    """Create a heatmap showing load per doctor per hour."""
    lines = []
    lines.append("Arzt-Heatmap (Auslastung pro Stunde)")
    lines.append("")
    hours = list(range(8, 18))
    header = "Arzt                    │" + "".join(f"{h:02d} " for h in hours)
    lines.append(header)
    lines.append("─" * 24 + "┼" + "─" * (len(hours) * 3))
    
    for doc in ctx.doctors:
        name = f"{doc.first_name} {doc.last_name}"[:22]
        hour_load = defaultdict(int)
        
        for apt in ctx.appointments:
            if apt.doctor_id == doc.id:
                start_hour = get_time_from_datetime(apt.start_time).hour
                end_hour = get_time_from_datetime(apt.end_time).hour
                for h in range(start_hour, min(end_hour + 1, 18)):
                    hour_load[h] += 1
        
        for op in ctx.operations:
            if op.primary_surgeon_id == doc.id or op.assistant_id == doc.id or op.anesthesist_id == doc.id:
                start_hour = get_time_from_datetime(op.start_time).hour
                end_hour = get_time_from_datetime(op.end_time).hour
                for h in range(start_hour, min(end_hour + 1, 18)):
                    hour_load[h] += 1
        
        cells = []
        for h in hours:
            load = hour_load[h]
            if load == 0:
                cells.append("·  ")
            elif load == 1:
                cells.append("░  ")
            elif load == 2:
                cells.append("▓█ ")
            else:
                cells.append("██ ")
        
        lines.append(f"{name:<22}  │{''.join(cells)}")
    
    lines.append("─" * 24 + "┴" + "─" * (len(hours) * 3))
    lines.append("Legende: · = frei  ░ = 1 Buchung  ▓█ = 2+ (Konflikt)")
    return "\n".join(lines)


def create_room_heatmap(ctx: VisualizationContext) -> str:
    """Create a heatmap showing load per room per hour."""
    lines = []
    lines.append("Raum-Heatmap (OP-Belegung pro Stunde)")
    lines.append("")
    hours = list(range(8, 18))
    header = "Raum                    │" + "".join(f"{h:02d} " for h in hours)
    lines.append(header)
    lines.append("─" * 24 + "┼" + "─" * (len(hours) * 3))
    
    for room in ctx.rooms:
        name = room.name[:22]
        hour_load = defaultdict(int)
        
        for op in ctx.operations:
            if op.op_room_id == room.id:
                start_hour = get_time_from_datetime(op.start_time).hour
                end_hour = get_time_from_datetime(op.end_time).hour
                for h in range(start_hour, min(end_hour + 1, 18)):
                    hour_load[h] += 1
        
        cells = []
        for h in hours:
            load = hour_load[h]
            if load == 0:
                cells.append("·  ")
            elif load == 1:
                cells.append("░  ")
            else:
                cells.append("█▓ ")
        
        lines.append(f"{name:<22}  │{''.join(cells)}")
    
    lines.append("─" * 24 + "┴" + "─" * (len(hours) * 3))
    lines.append("Legende: · = frei  ░ = belegt  █▓ = KONFLIKT")
    return "\n".join(lines)


# =============================================================================
# ABSENCE & WORKING HOURS VISUALIZATION
# =============================================================================

def visualize_absences(ctx: VisualizationContext) -> str:
    """Visualize doctor absences and conflicts."""
    lines = []
    
    for absence in ctx.absences:
        doc = absence.doctor
        lines.append(f"┌{'─' * 70}┐")
        lines.append(f"│ Arzt: {doc.first_name} {doc.last_name:<30} Grund: {absence.reason or 'k.A.':<15}│")
        lines.append(f"├{'─' * 70}┤")
        period = f"{absence.start_date} bis {absence.end_date}"
        lines.append(f"│ Abwesenheit: {period:<55}│")
        lines.append(f"│ {'█' * 50:<68}│")
        
        conflicts = [a for a in ctx.appointments 
                    if a.doctor_id == doc.id 
                    and absence.start_date <= get_date_from_datetime(a.start_time) <= absence.end_date]
        
        if conflicts:
            lines.append(f"│ ⚠ KONFLIKTE:{' ' * 56}│")
            for apt in conflicts:
                apt_date = get_date_from_datetime(apt.start_time)
                apt_start = get_time_from_datetime(apt.start_time)
                apt_end = get_time_from_datetime(apt.end_time)
                info = f"   Termin #{apt.id}: {apt_date} {apt_start.strftime('%H:%M')}-{apt_end.strftime('%H:%M')}"
                lines.append(f"│ {info:<68}│")
        else:
            lines.append(f"│ ✓ Keine Konflikte{' ' * 51}│")
        
        lines.append(f"└{'─' * 70}┘")
    
    return "\n".join(lines) if ctx.absences else "(keine Abwesenheiten)"


def visualize_working_hours(ctx: VisualizationContext) -> str:
    """Visualize working hours and violations."""
    lines = []
    lines.append("Praxis-Arbeitszeiten: 08:00 - 17:00")
    lines.append("")
    lines.append("  08:00" + "─" * 45 + "17:00")
    lines.append("    │" + "░" * 45 + "│  ← Arbeitszeit")
    lines.append("")
    
    violations = []
    for apt in ctx.appointments:
        apt_start = get_time_from_datetime(apt.start_time)
        apt_end = get_time_from_datetime(apt.end_time)
        if apt_start < time(8, 0) or apt_end > time(17, 0):
            violations.append({'apt': apt, 'type': 'before' if apt_start < time(8, 0) else 'after'})
    
    if violations:
        lines.append("⚠ ARBEITSZEITVERSTÖSSE:")
        for v in violations:
            apt = v['apt']
            apt_start = get_time_from_datetime(apt.start_time)
            apt_end = get_time_from_datetime(apt.end_time)
            if v['type'] == 'before':
                lines.append(f"  {apt_start.strftime('%H:%M')} ── Termin #{apt.id} ── {apt_end.strftime('%H:%M')}  VOR Beginn")
            else:
                lines.append(f"  {apt_start.strftime('%H:%M')} ── Termin #{apt.id} ── {apt_end.strftime('%H:%M')}  NACH Ende")
    else:
        lines.append("✓ Keine Arbeitszeitverstöße")
    
    return "\n".join(lines)


# =============================================================================
# EDGE CASES
# =============================================================================

def visualize_edge_cases() -> str:
    """Visualize common edge cases."""
    return """1. EDGE CASE: start_time == end_time (Null-Dauer)

   09:00 │ ← Start
   09:00 │ ← Ende
         ╳ UNGÜLTIG: Dauer = 0 Minuten

2. EDGE CASE: start_time > end_time (Negative Dauer)

   10:00 │ ← Start
   09:00 │ ← Ende
         ╳ UNGÜLTIG: Ende vor Start

3. EDGE CASE: Termin in der Vergangenheit

   Heute:  2025-12-29
   Termin: 2025-12-01
           ╳ UNGÜLTIG: Datum in der Vergangenheit

4. EDGE CASE: Ungültige Daten

   ┌─────────────────────────────────────┐
   │ Feld       │ Wert      │ Status     │
   ├─────────────────────────────────────┤
   │ patient_id │ null      │ ╳ REQUIRED │
   │ doctor_id  │ 999999    │ ╳ NOT FOUND│
   │ date       │ 'invalid' │ ╳ FORMAT   │
   └─────────────────────────────────────┘

5. EDGE CASE: Termin über Mitternacht

   23:00 ──── Termin ──── 01:00 (nächster Tag)
         ╳ NICHT UNTERSTÜTZT"""


# =============================================================================
# SUMMARY
# =============================================================================

def create_summary(ctx: VisualizationContext) -> str:
    """Create a summary of all conflicts."""
    conflicts = {'doctor_conflict': 0, 'room_conflict': 0, 'working_hours': 0, 'doctor_absent': 0, 'doctor_break': 0}
    
    for doc in ctx.doctors:
        appointments = [a for a in ctx.appointments if a.doctor_id == doc.id]
        for i, apt in enumerate(appointments):
            for j, other in enumerate(appointments):
                if i < j:
                    apt_start = get_time_from_datetime(apt.start_time)
                    apt_end = get_time_from_datetime(apt.end_time)
                    other_start = get_time_from_datetime(other.start_time)
                    other_end = get_time_from_datetime(other.end_time)
                    if apt_start < other_end and apt_end > other_start:
                        conflicts['doctor_conflict'] += 1
    
    for room in ctx.rooms:
        operations = [o for o in ctx.operations if o.op_room_id == room.id]
        for i, op in enumerate(operations):
            for j, other in enumerate(operations):
                if i < j:
                    op_start = get_time_from_datetime(op.start_time)
                    op_end = get_time_from_datetime(op.end_time)
                    other_start = get_time_from_datetime(other.start_time)
                    other_end = get_time_from_datetime(other.end_time)
                    if op_start < other_end and op_end > other_start:
                        conflicts['room_conflict'] += 1
    
    for apt in ctx.appointments:
        apt_start = get_time_from_datetime(apt.start_time)
        apt_end = get_time_from_datetime(apt.end_time)
        if apt_start < time(8, 0) or apt_end > time(17, 0):
            conflicts['working_hours'] += 1
    
    for absence in ctx.absences:
        for apt in ctx.appointments:
            apt_date = get_date_from_datetime(apt.start_time)
            if apt.doctor_id == absence.doctor_id and absence.start_date <= apt_date <= absence.end_date:
                conflicts['doctor_absent'] += 1
    
    for brk in ctx.breaks:
        for apt in ctx.appointments:
            apt_date = get_date_from_datetime(apt.start_time)
            apt_start = get_time_from_datetime(apt.start_time)
            apt_end = get_time_from_datetime(apt.end_time)
            if apt.doctor_id == brk.doctor_id and apt_date == brk.date:
                if apt_start < brk.end_time and apt_end > brk.start_time:
                    conflicts['doctor_break'] += 1
    
    total = sum(conflicts.values())
    high = conflicts['doctor_conflict'] + conflicts['room_conflict'] + conflicts['doctor_absent']
    medium = conflicts['working_hours'] + conflicts['doctor_break']
    
    lines = []
    lines.append("╔════════════════════════════════════════════════════════════════════════╗")
    lines.append("║                       KONFLIKT-ZUSAMMENFASSUNG                          ║")
    lines.append("╠════════════════════════════════════════════════════════════════════════╣")
    lines.append(f"║  Gesamtzahl Konflikte: {total:<50}║")
    lines.append("║                                                                        ║")
    lines.append("║  Nach Schweregrad:                                                     ║")
    lines.append(f"║    🔴 HOCH:   {high:<5} {'█' * min(high * 5, 40):<40}    ║")
    lines.append(f"║    🟡 MITTEL: {medium:<5} {'▓' * min(medium * 5, 40):<40}    ║")
    lines.append("║                                                                        ║")
    lines.append("║  Nach Kategorie:                                                       ║")
    for cat, count in sorted(conflicts.items(), key=lambda x: -x[1]):
        bar = "█" * min(count * 8, 35)
        lines.append(f"║    {cat:<18}: {count:>2}  {bar:<35}║")
    lines.append("║                                                                        ║")
    lines.append("╠════════════════════════════════════════════════════════════════════════╣")
    lines.append("║  EMPFEHLUNGEN:                                                         ║")
    if conflicts['doctor_conflict'] > 0:
        lines.append("║  • Arzt-Doppelbelegungen prüfen und umplanen                          ║")
    if conflicts['room_conflict'] > 0:
        lines.append("║  • OP-Raum-Konflikte auflösen (alternative Räume)                     ║")
    if conflicts['working_hours'] > 0:
        lines.append("║  • Termine außerhalb der Arbeitszeiten verschieben                    ║")
    if conflicts['doctor_absent'] > 0:
        lines.append("║  • Termine während Abwesenheiten auf Vertretung umbuchen              ║")
    if conflicts['doctor_break'] > 0:
        lines.append("║  • Pausen-Überschneidungen vermeiden                                  ║")
    if total == 0:
        lines.append("║  ✓ Keine Konflikte - System optimal konfiguriert                     ║")
    lines.append("╚════════════════════════════════════════════════════════════════════════╝")
    return "\n".join(lines)


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def generate_conflict_visualization(seed: int = None) -> str:
    """Generate complete conflict visualization."""
    ctx = VisualizationContext(seed=seed)
    ctx.setup()
    
    viz = ConflictVisualization(title="SCHEDULING-KONFLIKT-VISUALISIERUNG")
    viz.add_section("1. ARZT-KONFLIKTE (Zeitachsen)", visualize_doctor_conflicts(ctx))
    viz.add_section("2. RAUM-KONFLIKTE (Zeitachsen)", visualize_room_conflicts(ctx))
    viz.add_section("3. KONFLIKT-TABELLE", create_conflict_table(ctx))
    viz.add_section("4. KONFLIKTE NACH GRUPPEN", create_grouped_tables(ctx))
    viz.add_section("5. HEATMAP: Stündliche Auslastung", create_hourly_heatmap(ctx))
    viz.add_section("6. HEATMAP: Arzt-Auslastung", create_doctor_heatmap(ctx))
    viz.add_section("7. HEATMAP: Raum-Belegung", create_room_heatmap(ctx))
    viz.add_section("8. ABWESENHEITEN", visualize_absences(ctx))
    viz.add_section("9. ARBEITSZEIT-VERSTÖSSE", visualize_working_hours(ctx))
    viz.add_section("10. EDGE-CASES", visualize_edge_cases())
    viz.add_section("11. ZUSAMMENFASSUNG", create_summary(ctx))
    
    return viz.render()


def print_conflict_visualization(seed: int = None):
    """Print the complete visualization to stdout."""
    print(generate_conflict_visualization(seed))
