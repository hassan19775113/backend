"""Management command to calculate Ressourcen-KPIs (Teil 4/5)"""
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta, time
from collections import defaultdict
from praxi_backend.appointments.models import (
    Appointment, Operation, Resource, DoctorHours, DoctorAbsence, PracticeHours
)
from praxi_backend.core.models import User


class Command(BaseCommand):
    help = 'Calculate Ressourcen-KPIs (Teil 4/5)'

    def handle(self, *args, **options):
        # Load data
        appointments = list(Appointment.objects.using('default').select_related('doctor').all())
        operations = list(Operation.objects.using('default').select_related('primary_surgeon', 'op_room').all())
        rooms = list(Resource.objects.using('default').filter(type='room').all())
        doctors = list(User.objects.using('default').filter(role__name='doctor'))
        absences = list(DoctorAbsence.objects.using('default').all())
        practice_hours = list(PracticeHours.objects.using('default').all())
        doctor_hours = list(DoctorHours.objects.using('default').all())
        
        # Constants
        WORK_MINUTES_DAY = 540  # 9 Stunden
        WORK_DAYS_MONTH = 22
        TOTAL_CAPACITY = WORK_MINUTES_DAY * WORK_DAYS_MONTH  # 11880 min/Monat

        self.stdout.write('=' * 70)
        self.stdout.write('               RESSOURCEN-KPIs (Teil 4/5)')
        self.stdout.write('=' * 70)
        self.stdout.write('')

        # 1. ARZT-AUSLASTUNG
        doc_minutes = defaultdict(float)
        doc_appt_count = defaultdict(int)
        doc_op_count = defaultdict(int)
        
        for appt in appointments:
            if appt.doctor and appt.start_time and appt.end_time:
                dur = (appt.end_time - appt.start_time).total_seconds() / 60
                doc_minutes[appt.doctor_id] += dur
                doc_appt_count[appt.doctor_id] += 1
        
        for op in operations:
            if op.primary_surgeon and op.start_time and op.end_time:
                dur = (op.end_time - op.start_time).total_seconds() / 60
                doc_minutes[op.primary_surgeon_id] += dur
                doc_op_count[op.primary_surgeon_id] += 1

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 1. ARZT-AUSLASTUNG' + ' ' * 49 + '|')
        self.stdout.write('+' + '-' * 16 + '+' + '-' * 8 + '+' + '-' * 8 + '+' + '-' * 10 + '+' + '-' * 22 + '+')
        self.stdout.write('| Arzt           | Termin | OPs    | Ausl. %  | Visualisierung       |')
        self.stdout.write('+' + '-' * 16 + '+' + '-' * 8 + '+' + '-' * 8 + '+' + '-' * 10 + '+' + '-' * 22 + '+')

        doc_utils = []
        for doc in doctors:
            mins = doc_minutes.get(doc.id, 0)
            util = (mins / TOTAL_CAPACITY * 100) if TOTAL_CAPACITY > 0 else 0
            appts = doc_appt_count.get(doc.id, 0)
            ops = doc_op_count.get(doc.id, 0)
            doc_utils.append((doc.username, appts, ops, mins, util))
        
        doc_utils.sort(key=lambda x: -x[4])
        max_util = max(u[4] for u in doc_utils) if doc_utils else 1
        
        for name, appts, ops, mins, util in doc_utils:
            bar = '#' * int(util / max(max_util, 1) * 15)
            status = ' PEAK' if util == max_util and util > 0 else ''
            self.stdout.write(f'| {name:<14} |{appts:^8}|{ops:^8}|{util:>8.1f}% | {bar:<15}{status:>6}|')
        
        if doc_utils:
            avg_util = sum(u[4] for u in doc_utils) / len(doc_utils)
            self.stdout.write('+' + '-' * 16 + '+' + '-' * 8 + '+' + '-' * 8 + '+' + '-' * 10 + '+' + '-' * 22 + '+')
            self.stdout.write(f'| Durchschnitt   |        |        |{avg_util:>8.1f}% | {"~" * int(avg_util / max(max_util, 1) * 15):<21}|')
        
        self.stdout.write('+' + '-' * 16 + '+' + '-' * 8 + '+' + '-' * 8 + '+' + '-' * 10 + '+' + '-' * 22 + '+')
        self.stdout.write('')

        # 2. RAUM-AUSLASTUNG
        room_minutes = defaultdict(float)
        room_op_count = defaultdict(int)
        
        for op in operations:
            if op.op_room and op.start_time and op.end_time:
                dur = (op.end_time - op.start_time).total_seconds() / 60
                room_minutes[op.op_room_id] += dur
                room_op_count[op.op_room_id] += 1

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 2. RAUM-AUSLASTUNG' + ' ' * 49 + '|')
        self.stdout.write('+' + '-' * 18 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 17 + '+')
        self.stdout.write('| Raum             | OP-Anz   | Minuten  | Ausl. %  | Visualisierung  |')
        self.stdout.write('+' + '-' * 18 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 17 + '+')

        room_utils = []
        for room in rooms:
            mins = room_minutes.get(room.id, 0)
            util = (mins / TOTAL_CAPACITY * 100) if TOTAL_CAPACITY > 0 else 0
            ops = room_op_count.get(room.id, 0)
            room_utils.append((room.name, ops, mins, util))
        
        room_utils.sort(key=lambda x: -x[3])
        max_room_util = max(u[3] for u in room_utils) if room_utils else 1
        
        for name, ops, mins, util in room_utils:
            bar = '#' * int(util / max(max_room_util, 1) * 12)
            status = ' PEAK' if util == max_room_util and util > 0 else ''
            self.stdout.write(f'| {name:<16} |{ops:^10}|{mins:>8.0f}  |{util:>8.1f}% | {bar:<11}{status:>5}|')
        
        if room_utils:
            avg_room_util = sum(u[3] for u in room_utils) / len(room_utils)
            self.stdout.write('+' + '-' * 18 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 17 + '+')
            self.stdout.write(f'| Durchschnitt     |          |          |{avg_room_util:>8.1f}% | {"~" * int(avg_room_util / max(max_room_util, 1) * 12):<16}|')
        
        self.stdout.write('+' + '-' * 18 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 17 + '+')
        self.stdout.write('')

        # 3. ENGPASS-ANALYSE
        OVERLOAD_THRESHOLD = 80
        UNDERLOAD_THRESHOLD = 30
        
        overloaded_docs = [(n, u) for n, _, _, _, u in doc_utils if u > OVERLOAD_THRESHOLD]
        underloaded_docs = [(n, u) for n, _, _, _, u in doc_utils if u < UNDERLOAD_THRESHOLD]
        overloaded_rooms = [(n, u) for n, _, _, u in room_utils if u > OVERLOAD_THRESHOLD]
        underloaded_rooms = [(n, u) for n, _, _, u in room_utils if u < UNDERLOAD_THRESHOLD]

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 3. ENGPASS-ANALYSE' + ' ' * 49 + '|')
        self.stdout.write('+' + '-' * 68 + '+')
        
        self.stdout.write(f'|  Ueberlastete Aerzte (>{OVERLOAD_THRESHOLD}%):' + ' ' * 41 + '|')
        if overloaded_docs:
            for name, util in overloaded_docs[:3]:
                bar = '#' * int(util / 100 * 20)
                self.stdout.write(f'|    {name:<14} {util:>5.1f}%  {bar:<30}      !!! |')
        else:
            self.stdout.write('|    (keine)' + ' ' * 56 + '|')
        
        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write(f'|  Ueberlastete Raeume (>{OVERLOAD_THRESHOLD}%):' + ' ' * 40 + '|')
        if overloaded_rooms:
            for name, util in overloaded_rooms[:3]:
                bar = '#' * int(util / 100 * 20)
                self.stdout.write(f'|    {name:<14} {util:>5.1f}%  {bar:<30}      !!! |')
        else:
            self.stdout.write('|    (keine)' + ' ' * 56 + '|')
        
        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write(f'|  Unterlastete Ressourcen (<{UNDERLOAD_THRESHOLD}%):' + ' ' * 35 + '|')
        under_all = underloaded_docs + underloaded_rooms
        if under_all:
            for name, util in under_all[:4]:
                bar = '.' * int(util / 100 * 20)
                self.stdout.write(f'|    {name:<14} {util:>5.1f}%  {bar:<35}     |')
        else:
            self.stdout.write('|    (keine)' + ' ' * 56 + '|')
        
        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('')

        # 4. ARBEITSZEIT-NUTZUNG PRO ARZT
        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 4. ARBEITSZEIT-NUTZUNG PRO ARZT' + ' ' * 35 + '|')
        self.stdout.write('+' + '-' * 16 + '+' + '-' * 12 + '+' + '-' * 12 + '+' + '-' * 25 + '+')
        self.stdout.write('| Arzt           | Gebucht    | Verfuegbar | Nutzung                 |')
        self.stdout.write('+' + '-' * 16 + '+' + '-' * 12 + '+' + '-' * 12 + '+' + '-' * 25 + '+')

        for name, appts, ops, mins, util in doc_utils:
            avail = TOTAL_CAPACITY
            usage_pct = (mins / avail * 100) if avail > 0 else 0
            bar_used = '#' * int(usage_pct / 100 * 15)
            bar_free = '.' * (15 - len(bar_used))
            self.stdout.write(f'| {name:<14} |{mins:>8.0f} min|{avail:>8} min| [{bar_used}{bar_free}] {usage_pct:>5.1f}%|')
        
        self.stdout.write('+' + '-' * 16 + '+' + '-' * 12 + '+' + '-' * 12 + '+' + '-' * 25 + '+')
        self.stdout.write('')

        # 5. ABWESENHEITSQUOTE PRO ARZT
        today = datetime.now().date()
        month_start = today.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        doc_absence_days = defaultdict(int)
        for absence in absences:
            start = max(absence.start_date, month_start)
            end = min(absence.end_date, month_end)
            if start <= end:
                days = (end - start).days + 1
                doc_absence_days[absence.doctor_id] += days

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 5. ABWESENHEITSQUOTE PRO ARZT (aktueller Monat)' + ' ' * 20 + '|')
        self.stdout.write('+' + '-' * 16 + '+' + '-' * 12 + '+' + '-' * 12 + '+' + '-' * 25 + '+')
        self.stdout.write('| Arzt           | Abw. Tage  | Quote %    | Visualisierung          |')
        self.stdout.write('+' + '-' * 16 + '+' + '-' * 12 + '+' + '-' * 12 + '+' + '-' * 25 + '+')

        for doc in doctors:
            days = doc_absence_days.get(doc.id, 0)
            quote = (days / WORK_DAYS_MONTH * 100) if WORK_DAYS_MONTH > 0 else 0
            bar = 'X' * int(quote / 100 * 15)
            bar_ok = '.' * (15 - len(bar))
            status = ' HOCH!' if quote > 20 else ''
            self.stdout.write(f'| {doc.username:<14} |{days:^12}|{quote:>10.1f}% | [{bar}{bar_ok}]{status:>6}|')
        
        self.stdout.write('+' + '-' * 16 + '+' + '-' * 12 + '+' + '-' * 12 + '+' + '-' * 25 + '+')
        self.stdout.write('')

        # 6. VERFUEGBARE VS. BELEGTE SLOTS
        total_appts = len(appointments)
        total_ops = len(operations)
        total_booked = total_appts + total_ops
        
        # Schätze verfügbare Slots (30 min Slots pro Arzt pro Tag)
        slots_per_day = WORK_MINUTES_DAY // 30  # 18 Slots pro Tag
        total_available_slots = slots_per_day * WORK_DAYS_MONTH * len(doctors)
        
        # OP-Slots (2h Slots pro Raum)
        op_slots_per_day = WORK_MINUTES_DAY // 120  # 4.5 -> 4 Slots
        total_op_slots = op_slots_per_day * WORK_DAYS_MONTH * len(rooms)
        
        total_slots = total_available_slots + total_op_slots
        booking_rate = (total_booked / total_slots * 100) if total_slots > 0 else 0
        free_slots = total_slots - total_booked

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 6. SLOT-VERFUEGBARKEIT' + ' ' * 45 + '|')
        self.stdout.write('+' + '-' * 30 + '+' + '-' * 15 + '+' + '-' * 20 + '+')
        self.stdout.write('| Metrik                       |     Wert      | Visualisierung     |')
        self.stdout.write('+' + '-' * 30 + '+' + '-' * 15 + '+' + '-' * 20 + '+')
        
        self.stdout.write(f'| Termin-Slots (gesamt)        |{total_available_slots:>13}  |                    |')
        self.stdout.write(f'| OP-Slots (gesamt)            |{total_op_slots:>13}  |                    |')
        self.stdout.write(f'| Gesamt verfuegbar            |{total_slots:>13}  |                    |')
        self.stdout.write('+' + '-' * 30 + '+' + '-' * 15 + '+' + '-' * 20 + '+')
        self.stdout.write(f'| Termine gebucht              |{total_appts:>13}  |                    |')
        self.stdout.write(f'| OPs gebucht                  |{total_ops:>13}  |                    |')
        self.stdout.write(f'| Gesamt belegt                |{total_booked:>13}  |                    |')
        self.stdout.write('+' + '-' * 30 + '+' + '-' * 15 + '+' + '-' * 20 + '+')
        
        bar_booked = '#' * int(booking_rate / 100 * 15)
        bar_free = '.' * (15 - len(bar_booked))
        self.stdout.write(f'| Belegungsrate                |{booking_rate:>12.1f}%  | [{bar_booked}{bar_free}] |')
        self.stdout.write(f'| Freie Slots                  |{free_slots:>13}  |                    |')
        self.stdout.write('+' + '-' * 30 + '+' + '-' * 15 + '+' + '-' * 20 + '+')
        self.stdout.write('')

        # ZUSAMMENFASSUNG
        self.stdout.write('=' * 70)
        self.stdout.write('                    ZUSAMMENFASSUNG')
        self.stdout.write('=' * 70)
        if doc_utils:
            self.stdout.write(f'  * Aerzte:               {len(doctors)}')
            self.stdout.write(f'  * Raeume:               {len(rooms)}')
            self.stdout.write(f'  * Ø Arzt-Auslastung:    {avg_util:.1f}%')
        if room_utils:
            self.stdout.write(f'  * Ø Raum-Auslastung:    {avg_room_util:.1f}%')
        self.stdout.write(f'  * Ueberlastete Aerzte:  {len(overloaded_docs)}')
        self.stdout.write(f'  * Ueberlastete Raeume:  {len(overloaded_rooms)}')
        self.stdout.write(f'  * Belegungsrate:        {booking_rate:.1f}%')
        self.stdout.write(f'  * Freie Slots:          {free_slots}')
        
        self.stdout.write('')
        self.stdout.write('  BEWERTUNG:')
        if avg_util < 50:
            self.stdout.write('  -> Arzt-Kapazitaet: UNTERAUSGELASTET - mehr Termine moeglich')
        elif avg_util < 80:
            self.stdout.write('  -> Arzt-Kapazitaet: OPTIMAL')
        else:
            self.stdout.write('  -> Arzt-Kapazitaet: UEBERLASTET - Entlastung noetig!')
        
        if avg_room_util < 50:
            self.stdout.write('  -> Raum-Kapazitaet: UNTERAUSGELASTET')
        elif avg_room_util < 80:
            self.stdout.write('  -> Raum-Kapazitaet: OPTIMAL')
        else:
            self.stdout.write('  -> Raum-Kapazitaet: ENGPASS - mehr Raeume noetig!')
        
        self.stdout.write('=' * 70)
