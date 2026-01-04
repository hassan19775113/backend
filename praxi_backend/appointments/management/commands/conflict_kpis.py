"""Management command to calculate Konflikt-KPIs (Teil 3/5)"""
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from collections import defaultdict
from praxi_backend.appointments.models import (
    Appointment, Operation, Resource, DoctorHours, DoctorAbsence, DoctorBreak, PracticeHours
)
from praxi_backend.core.models import User


class Command(BaseCommand):
    help = 'Calculate Konflikt-KPIs (Teil 3/5)'

    def detect_conflicts(self):
        """Detect all conflicts in the system"""
        appointments = list(Appointment.objects.using('default').select_related('doctor', 'type').all())
        operations = list(Operation.objects.using('default').select_related('primary_surgeon', 'op_room').all())
        absences = list(DoctorAbsence.objects.using('default').all())
        
        conflicts = []
        
        # 1. Doctor conflicts (same doctor, overlapping times)
        doc_appts = defaultdict(list)
        for appt in appointments:
            if appt.doctor and appt.start_time and appt.end_time:
                doc_appts[appt.doctor_id].append(appt)
        
        for doc_id, appts in doc_appts.items():
            appts_sorted = sorted(appts, key=lambda x: x.start_time)
            for i in range(len(appts_sorted) - 1):
                a1, a2 = appts_sorted[i], appts_sorted[i + 1]
                if a1.end_time > a2.start_time:
                    conflicts.append({
                        'type': 'doctor_conflict',
                        'doctor_id': doc_id,
                        'hour': a1.start_time.hour,
                        'items': [a1, a2]
                    })
        
        # 2. Doctor conflicts from operations
        doc_ops = defaultdict(list)
        for op in operations:
            if op.primary_surgeon and op.start_time and op.end_time:
                doc_ops[op.primary_surgeon_id].append(op)
        
        for doc_id, ops in doc_ops.items():
            ops_sorted = sorted(ops, key=lambda x: x.start_time)
            for i in range(len(ops_sorted) - 1):
                o1, o2 = ops_sorted[i], ops_sorted[i + 1]
                if o1.end_time > o2.start_time:
                    conflicts.append({
                        'type': 'operation_overlap',
                        'doctor_id': doc_id,
                        'hour': o1.start_time.hour,
                        'items': [o1, o2]
                    })
        
        # 3. Room conflicts
        room_ops = defaultdict(list)
        for op in operations:
            if op.op_room and op.start_time and op.end_time:
                room_ops[op.op_room_id].append(op)
        
        for room_id, ops in room_ops.items():
            ops_sorted = sorted(ops, key=lambda x: x.start_time)
            for i in range(len(ops_sorted) - 1):
                o1, o2 = ops_sorted[i], ops_sorted[i + 1]
                if o1.end_time > o2.start_time:
                    conflicts.append({
                        'type': 'room_conflict',
                        'room_id': room_id,
                        'hour': o1.start_time.hour,
                        'items': [o1, o2]
                    })
        
        # 4. Appointment overlaps (same timeslot issues)
        for i, a1 in enumerate(appointments):
            if not (a1.start_time and a1.end_time):
                continue
            for a2 in appointments[i+1:]:
                if not (a2.start_time and a2.end_time):
                    continue
                if a1.doctor_id == a2.doctor_id:
                    continue  # Already counted
                # Check if same room resource
                if hasattr(a1, 'room') and hasattr(a2, 'room') and a1.room == a2.room:
                    if a1.start_time < a2.end_time and a2.start_time < a1.end_time:
                        conflicts.append({
                            'type': 'appointment_overlap',
                            'hour': a1.start_time.hour,
                            'items': [a1, a2]
                        })
        
        # 5. Working hours violations
        practice_hours = {ph.weekday: ph for ph in PracticeHours.objects.using('default').all()}
        for appt in appointments:
            if not (appt.start_time and appt.end_time):
                continue
            weekday = appt.start_time.weekday()
            ph = practice_hours.get(weekday)
            if ph:
                appt_start = appt.start_time.time()
                appt_end = appt.end_time.time()
                if appt_start < ph.start_time or appt_end > ph.end_time:
                    conflicts.append({
                        'type': 'working_hours_violation',
                        'doctor_id': appt.doctor_id,
                        'hour': appt.start_time.hour,
                        'items': [appt]
                    })
        
        for op in operations:
            if not (op.start_time and op.end_time):
                continue
            weekday = op.start_time.weekday()
            ph = practice_hours.get(weekday)
            if ph:
                op_start = op.start_time.time()
                op_end = op.end_time.time()
                if op_start < ph.start_time or op_end > ph.end_time:
                    conflicts.append({
                        'type': 'working_hours_violation',
                        'doctor_id': op.primary_surgeon_id,
                        'hour': op.start_time.hour,
                        'items': [op]
                    })
        
        # 6. Doctor absent conflicts
        for appt in appointments:
            if not (appt.doctor and appt.start_time):
                continue
            for absence in absences:
                if absence.doctor_id == appt.doctor_id:
                    if absence.start_date <= appt.start_time.date() <= absence.end_date:
                        conflicts.append({
                            'type': 'doctor_absent',
                            'doctor_id': appt.doctor_id,
                            'hour': appt.start_time.hour,
                            'items': [appt, absence]
                        })
        
        for op in operations:
            if not (op.primary_surgeon and op.start_time):
                continue
            for absence in absences:
                if absence.doctor_id == op.primary_surgeon_id:
                    if absence.start_date <= op.start_time.date() <= absence.end_date:
                        conflicts.append({
                            'type': 'doctor_absent',
                            'doctor_id': op.primary_surgeon_id,
                            'hour': op.start_time.hour,
                            'items': [op, absence]
                        })
        
        # 7. Edge cases (appointments at unusual times)
        for appt in appointments:
            if appt.start_time:
                hour = appt.start_time.hour
                if hour < 7 or hour >= 20:
                    conflicts.append({
                        'type': 'edge_cases',
                        'hour': hour,
                        'items': [appt]
                    })
        
        return conflicts, len(appointments), len(operations)

    def handle(self, *args, **options):
        conflicts, appt_count, op_count = self.detect_conflicts()
        
        self.stdout.write('=' * 70)
        self.stdout.write('                 KONFLIKT-KPIs (Teil 3/5)')
        self.stdout.write('=' * 70)
        self.stdout.write('')

        total_conflicts = len(conflicts)
        
        # 1. KONFLIKTE PRO 100 PLANUNGEN
        conf_per_100_appts = (total_conflicts / appt_count * 100) if appt_count > 0 else 0
        conf_per_100_ops = (total_conflicts / op_count * 100) if op_count > 0 else 0
        total_plannings = appt_count + op_count
        conf_per_100_total = (total_conflicts / total_plannings * 100) if total_plannings > 0 else 0

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 1. KONFLIKTE PRO 100 PLANUNGEN' + ' ' * 36 + '|')
        self.stdout.write('+' + '-' * 30 + '+' + '-' * 12 + '+' + '-' * 23 + '+')
        self.stdout.write('| Metrik                       |    Wert    | Bewertung             |')
        self.stdout.write('+' + '-' * 30 + '+' + '-' * 12 + '+' + '-' * 23 + '+')
        
        def rating(val):
            if val < 5: return 'GUT'
            elif val < 20: return 'AKZEPTABEL'
            elif val < 50: return 'KRITISCH'
            else: return 'SEHR KRITISCH'
        
        self.stdout.write(f'| Konflikte / 100 Termine      |{conf_per_100_appts:>10.1f}  | {rating(conf_per_100_appts):<21} |')
        self.stdout.write(f'| Konflikte / 100 OPs          |{conf_per_100_ops:>10.1f}  | {rating(conf_per_100_ops):<21} |')
        self.stdout.write(f'| Konflikte / 100 Gesamt       |{conf_per_100_total:>10.1f}  | {rating(conf_per_100_total):<21} |')
        self.stdout.write('+' + '-' * 30 + '+' + '-' * 12 + '+' + '-' * 23 + '+')
        self.stdout.write('')

        # 2. KONFLIKTE PRO ARZT
        doc_conflicts = defaultdict(int)
        for c in conflicts:
            doc_id = c.get('doctor_id')
            if doc_id:
                doc_conflicts[doc_id] += 1
        
        doctors = {u.id: u.username for u in User.objects.using('default').filter(role__name='doctor')}
        
        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 2. KONFLIKTE PRO ARZT' + ' ' * 46 + '|')
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 10 + '+' + '-' * 35 + '+')
        self.stdout.write('| Arzt               |  Anzahl  | Visualisierung                    |')
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 10 + '+' + '-' * 35 + '+')
        
        doc_stats = [(doctors.get(d, f'ID:{d}'), c) for d, c in doc_conflicts.items()]
        doc_stats.sort(key=lambda x: -x[1])
        max_doc = max(c for _, c in doc_stats) if doc_stats else 1
        
        for name, count in doc_stats[:6]:
            bar = '#' * int(count / max_doc * 25)
            peak = ' <- TOP' if count == max_doc else ''
            self.stdout.write(f'| {name:<18} |{count:^10}| {bar:<27}{peak:>7}|')
        
        if not doc_stats:
            self.stdout.write('| (keine Konflikte)  |    0     |                                   |')
        
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 10 + '+' + '-' * 35 + '+')
        self.stdout.write('')

        # 3. KONFLIKTE PRO RAUM
        room_conflicts = defaultdict(int)
        for c in conflicts:
            room_id = c.get('room_id')
            if room_id:
                room_conflicts[room_id] += 1
        
        rooms = {r.id: r.name for r in Resource.objects.using('default').filter(type='room')}
        
        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 3. KONFLIKTE PRO RAUM' + ' ' * 46 + '|')
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 10 + '+' + '-' * 35 + '+')
        self.stdout.write('| Raum               |  Anzahl  | Visualisierung                    |')
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 10 + '+' + '-' * 35 + '+')
        
        room_stats = [(rooms.get(r, f'ID:{r}'), c) for r, c in room_conflicts.items()]
        room_stats.sort(key=lambda x: -x[1])
        max_room = max(c for _, c in room_stats) if room_stats else 1
        
        for name, count in room_stats[:6]:
            bar = '#' * int(count / max_room * 25)
            peak = ' <- TOP' if count == max_room else ''
            self.stdout.write(f'| {name:<18} |{count:^10}| {bar:<27}{peak:>7}|')
        
        if not room_stats:
            self.stdout.write('| (keine Konflikte)  |    0     |                                   |')
        
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 10 + '+' + '-' * 35 + '+')
        self.stdout.write('')

        # 4. KONFLIKTVERTEILUNG NACH TYP
        type_counts = defaultdict(int)
        for c in conflicts:
            type_counts[c['type']] += 1
        
        type_labels = {
            'doctor_conflict': 'Arzt-Konflikt',
            'room_conflict': 'Raum-Konflikt',
            'appointment_overlap': 'Termin-Overlap',
            'operation_overlap': 'OP-Overlap',
            'working_hours_violation': 'Arbeitszeit-Verstoss',
            'doctor_absent': 'Arzt abwesend',
            'edge_cases': 'Randzeiten'
        }
        
        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 4. KONFLIKTVERTEILUNG NACH TYP' + ' ' * 36 + '|')
        self.stdout.write('+' + '-' * 25 + '+' + '-' * 8 + '+' + '-' * 8 + '+' + '-' * 24 + '+')
        self.stdout.write('| Konflikt-Typ              | Anzahl |   %    | Visualisierung         |')
        self.stdout.write('+' + '-' * 25 + '+' + '-' * 8 + '+' + '-' * 8 + '+' + '-' * 24 + '+')
        
        max_type = max(type_counts.values()) if type_counts else 1
        for typ in ['doctor_conflict', 'room_conflict', 'appointment_overlap', 
                    'operation_overlap', 'working_hours_violation', 'doctor_absent', 'edge_cases']:
            count = type_counts.get(typ, 0)
            pct = (count / total_conflicts * 100) if total_conflicts > 0 else 0
            bar = '#' * int(count / max_type * 15) if max_type > 0 else ''
            label = type_labels.get(typ, typ)[:23]
            self.stdout.write(f'| {label:<23}   |{count:^8}|{pct:>6.1f}% | {bar:<22} |')
        
        self.stdout.write('+' + '-' * 25 + '+' + '-' * 8 + '+' + '-' * 8 + '+' + '-' * 24 + '+')
        self.stdout.write('')

        # 5. KONFLIKT-HEATMAP (0-23 Uhr)
        hour_conflicts = defaultdict(int)
        for c in conflicts:
            hour = c.get('hour', 0)
            hour_conflicts[hour] += 1
        
        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 5. KONFLIKT-HEATMAP (Stunde 0-23)' + ' ' * 33 + '|')
        self.stdout.write('+' + '-' * 68 + '+')
        
        max_hour = max(hour_conflicts.values()) if hour_conflicts else 1
        
        # Header
        header = '|     |'
        for h in range(24):
            header += f'{h:2}|'
        self.stdout.write(header)
        self.stdout.write('+' + '-' * 5 + '+' + '-' * 72[:62] + '+')
        
        # Heat row
        heat_chars = [' ', '.', 'o', 'O', '#', '@']
        row = '| Konf|'
        for h in range(24):
            count = hour_conflicts.get(h, 0)
            if max_hour > 0:
                intensity = int(count / max_hour * 5)
            else:
                intensity = 0
            row += f' {heat_chars[min(intensity, 5)]}|'
        self.stdout.write(row)
        
        # Count row
        count_row = '| Anz |'
        for h in range(24):
            count = hour_conflicts.get(h, 0)
            if count > 99:
                count_row += '99|'
            else:
                count_row += f'{count:2}|'
        self.stdout.write(count_row)
        
        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('  Legende: [ ]=0  [.]=wenig  [o]=mittel  [O]=hoch  [#]=sehr hoch  [@]=max')
        self.stdout.write('')

        # 6. ZUSAMMENFASSUNG
        self.stdout.write('=' * 70)
        self.stdout.write('                    ZUSAMMENFASSUNG')
        self.stdout.write('=' * 70)
        self.stdout.write(f'  * Gesamt-Konflikte:     {total_conflicts}')
        self.stdout.write(f'  * Termine:              {appt_count}')
        self.stdout.write(f'  * Operationen:          {op_count}')
        self.stdout.write(f'  * Konfl./100 Planungen: {conf_per_100_total:.1f}')
        
        if type_counts:
            top_type = max(type_counts.items(), key=lambda x: x[1])
            self.stdout.write(f'  * Haeufigster Typ:      {type_labels.get(top_type[0], top_type[0])} ({top_type[1]})')
        
        peak_hours = sorted(hour_conflicts.items(), key=lambda x: -x[1])[:3]
        if peak_hours:
            peaks = ', '.join(f'{h:02d}:00' for h, _ in peak_hours)
            self.stdout.write(f'  * Peak-Stunden:         {peaks}')
        
        # Interpretation
        self.stdout.write('')
        self.stdout.write('  INTERPRETATION:')
        if conf_per_100_total < 5:
            self.stdout.write('  -> Scheduling-Qualitaet: SEHR GUT')
        elif conf_per_100_total < 20:
            self.stdout.write('  -> Scheduling-Qualitaet: GUT')
        elif conf_per_100_total < 50:
            self.stdout.write('  -> Scheduling-Qualitaet: VERBESSERUNGSWUERDIG')
        else:
            self.stdout.write('  -> Scheduling-Qualitaet: KRITISCH - Optimierung erforderlich!')
        
        self.stdout.write('=' * 70)
