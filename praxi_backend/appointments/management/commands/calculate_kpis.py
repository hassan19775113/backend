"""
Management command to calculate scheduling KPIs.

Usage:
    python manage.py calculate_kpis
    python manage.py calculate_kpis --part 1
    python manage.py calculate_kpis --output kpis.txt
"""

from collections import defaultdict
from datetime import timedelta
from statistics import mean, median

from django.core.management.base import BaseCommand
from django.utils import timezone

from praxi_backend.appointments.models import (
    Appointment,
    DoctorAbsence,
    DoctorBreak,
    Operation,
    Resource,
)
from praxi_backend.core.models import User


class Command(BaseCommand):
    help = "Calculate scheduling KPIs"

    def add_arguments(self, parser):
        parser.add_argument("--part", type=int, default=0, help="KPI part (1-4, 0=all)")
        parser.add_argument("--output", type=str, default=None, help="Output file")

    def handle(self, *args, **options):
        part = options.get("part", 0)
        output_file = options.get("output")

        # Load data
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        month_start = today.replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        appointments = list(Appointment.objects.using('default').all())
        operations = list(Operation.objects.using('default').all())
        doctors = list(User.objects.using('default').filter(role__name='doctor'))
        rooms = list(Resource.objects.using('default').filter(type='room', active=True))

        output = []

        if part == 0 or part == 1:
            output.append(self.generate_part1(appointments, operations, today, week_start, week_end, month_start, month_end))

        if part == 0 or part == 2:
            output.append(self.generate_part2(appointments, operations, doctors, rooms))

        if part == 0 or part == 3:
            output.append(self.generate_part3(appointments, operations, doctors))

        if part == 0 or part == 4:
            output.append(self.generate_part4(appointments, operations))

        content = "\n\n".join(output)

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)
            self.stdout.write(self.style.SUCCESS(f"✓ KPIs written to: {output_file}"))
        else:
            self.stdout.write(content)

    def generate_part1(self, appointments, operations, today, week_start, week_end, month_start, month_end):
        """Teil 1: Mengen, Dauern, Peak-Stunden/Tage"""
        lines = []
        lines.append("╔════════════════════════════════════════════════════════════════════════╗")
        lines.append("║                    SCHEDULING KPIs (Teil 1/4)                          ║")
        lines.append("╚════════════════════════════════════════════════════════════════════════╝")
        lines.append("")

        # 1. Mengen
        lines.append("┌────────────────────────────────────────────────────────────────────────┐")
        lines.append("│  1. MENGEN-ÜBERSICHT                                                   │")
        lines.append("├──────────────────────┬──────────┬──────────┬──────────┬────────────────┤")
        lines.append("│ Metrik               │   Tag    │  Woche   │  Monat   │ Gesamt         │")
        lines.append("├──────────────────────┼──────────┼──────────┼──────────┼────────────────┤")

        day_apts = len([a for a in appointments if a.start_time.date() == today])
        week_apts = len([a for a in appointments if week_start <= a.start_time.date() <= week_end])
        month_apts = len([a for a in appointments if month_start <= a.start_time.date() <= month_end])
        total_apts = len(appointments)

        day_ops = len([o for o in operations if o.start_time.date() == today])
        week_ops = len([o for o in operations if week_start <= o.start_time.date() <= week_end])
        month_ops = len([o for o in operations if month_start <= o.start_time.date() <= month_end])
        total_ops = len(operations)

        lines.append(f"│ Termine              │{day_apts:^10}│{week_apts:^10}│{month_apts:^10}│{total_apts:^16}│")
        lines.append(f"│ Operationen          │{day_ops:^10}│{week_ops:^10}│{month_ops:^10}│{total_ops:^16}│")
        lines.append(f"│ GESAMT               │{day_apts+day_ops:^10}│{week_apts+week_ops:^10}│{month_apts+month_ops:^10}│{total_apts+total_ops:^16}│")
        lines.append("└──────────────────────┴──────────┴──────────┴──────────┴────────────────┘")
        lines.append("")

        # 2. Dauern
        lines.append("┌────────────────────────────────────────────────────────────────────────┐")
        lines.append("│  2. DAUER-STATISTIKEN                                                  │")
        lines.append("├──────────────────────┬──────────┬──────────┬──────────┬────────────────┤")
        lines.append("│ Metrik               │    Ø     │  Median  │   Min    │      Max       │")
        lines.append("├──────────────────────┼──────────┼──────────┼──────────┼────────────────┤")

        apt_durations = [(a.end_time - a.start_time).total_seconds() / 60 for a in appointments if a.end_time and a.start_time]
        op_durations = [(o.end_time - o.start_time).total_seconds() / 60 for o in operations if o.end_time and o.start_time]

        if apt_durations:
            apt_avg, apt_med, apt_min, apt_max = mean(apt_durations), median(apt_durations), min(apt_durations), max(apt_durations)
            lines.append(f"│ Terminlänge (min)    │{apt_avg:^10.1f}│{apt_med:^10.1f}│{apt_min:^10.1f}│{apt_max:^16.1f}│")
        else:
            lines.append(f"│ Terminlänge (min)    │{'--':^10}│{'--':^10}│{'--':^10}│{'--':^16}│")

        if op_durations:
            op_avg, op_med, op_min, op_max = mean(op_durations), median(op_durations), min(op_durations), max(op_durations)
            lines.append(f"│ OP-Dauer (min)       │{op_avg:^10.1f}│{op_med:^10.1f}│{op_min:^10.1f}│{op_max:^16.1f}│")
        else:
            lines.append(f"│ OP-Dauer (min)       │{'--':^10}│{'--':^10}│{'--':^10}│{'--':^16}│")

        lines.append("└──────────────────────┴──────────┴──────────┴──────────┴────────────────┘")
        lines.append("")

        # 3. Peak-Stunden
        lines.append("┌────────────────────────────────────────────────────────────────────────┐")
        lines.append("│  3. PEAK-STUNDEN                                                       │")
        lines.append("├────────┬──────────┬─────────────────────────────────────────────────────┤")
        lines.append("│ Stunde │  Anzahl  │ Verteilung                                         │")
        lines.append("├────────┼──────────┼─────────────────────────────────────────────────────┤")

        hour_counts = defaultdict(int)
        for a in appointments:
            hour_counts[a.start_time.hour] += 1
        for o in operations:
            hour_counts[o.start_time.hour] += 1

        max_count = max(hour_counts.values()) if hour_counts else 1
        for hour in range(8, 18):
            count = hour_counts.get(hour, 0)
            bar_len = int(count / max_count * 40) if max_count > 0 else 0
            bar = "█" * bar_len
            peak = " ← PEAK" if count == max_count and count > 0 else ""
            lines.append(f"│ {hour:02d}:00  │{count:^10}│ {bar:<40}{peak:>8}│")

        lines.append("└────────┴──────────┴─────────────────────────────────────────────────────┘")
        lines.append("")

        # 4. Peak-Tage
        lines.append("┌────────────────────────────────────────────────────────────────────────┐")
        lines.append("│  4. PEAK-TAGE (Woche)                                                  │")
        lines.append("├────────┬──────────┬─────────────────────────────────────────────────────┤")
        lines.append("│  Tag   │  Anzahl  │ Verteilung                                         │")
        lines.append("├────────┼──────────┼─────────────────────────────────────────────────────┤")

        weekday_counts = defaultdict(int)
        for a in appointments:
            weekday_counts[a.start_time.weekday()] += 1
        for o in operations:
            weekday_counts[o.start_time.weekday()] += 1

        weekdays = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
        max_day = max(weekday_counts.values()) if weekday_counts else 1
        for wd in range(7):
            count = weekday_counts.get(wd, 0)
            bar_len = int(count / max_day * 40) if max_day > 0 else 0
            bar = "█" * bar_len
            peak = " ← PEAK" if count == max_day and count > 0 else ""
            lines.append(f"│   {weekdays[wd]}   │{count:^10}│ {bar:<40}{peak:>8}│")

        lines.append("└────────┴──────────┴─────────────────────────────────────────────────────┘")

        return "\n".join(lines)

    def generate_part2(self, appointments, operations, doctors, rooms):
        """Teil 2: Auslastung Ärzte & Räume"""
        lines = []
        lines.append("╔════════════════════════════════════════════════════════════════════════╗")
        lines.append("║                    SCHEDULING KPIs (Teil 2/4)                          ║")
        lines.append("╚════════════════════════════════════════════════════════════════════════╝")
        lines.append("")

        # Arzt-Auslastung
        lines.append("┌────────────────────────────────────────────────────────────────────────┐")
        lines.append("│  5. ARZT-AUSLASTUNG                                                    │")
        lines.append("├────────────────────────┬────────┬────────┬──────────────────────────────┤")
        lines.append("│ Arzt                   │Termine │  OPs   │ Auslastung                   │")
        lines.append("├────────────────────────┼────────┼────────┼──────────────────────────────┤")

        doc_stats = []
        for doc in doctors:
            apt_count = len([a for a in appointments if a.doctor_id == doc.id])
            op_count = len([o for o in operations if o.primary_surgeon_id == doc.id])
            util = min(100, (apt_count + op_count) * 10)
            doc_stats.append((doc, apt_count, op_count, util))

        for doc, apt_count, op_count, util in sorted(doc_stats, key=lambda x: -x[3]):
            name = f"{doc.first_name} {doc.last_name}"[:22]
            bar_len = int(util / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"│ {name:<22} │{apt_count:^8}│{op_count:^8}│ {bar} {util:5.1f}%│")

        if doc_stats:
            avg_util = sum(d[3] for d in doc_stats) / len(doc_stats)
            bar_len = int(avg_util / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append("├────────────────────────┼────────┼────────┼──────────────────────────────┤")
            lines.append(f"│ DURCHSCHNITT           │{'--':^8}│{'--':^8}│ {bar} {avg_util:5.1f}%│")

        lines.append("└────────────────────────┴────────┴────────┴──────────────────────────────┘")
        lines.append("")

        # Raum-Auslastung
        lines.append("┌────────────────────────────────────────────────────────────────────────┐")
        lines.append("│  6. RAUM-AUSLASTUNG                                                    │")
        lines.append("├────────────────────────┬────────┬──────────────────────────────────────┤")
        lines.append("│ Raum                   │  OPs   │ Auslastung                           │")
        lines.append("├────────────────────────┼────────┼──────────────────────────────────────┤")

        room_stats = []
        for room in rooms:
            op_count = len([o for o in operations if o.op_room_id == room.id])
            util = min(100, op_count * 20)
            room_stats.append((room, op_count, util))

        for room, op_count, util in sorted(room_stats, key=lambda x: -x[2]):
            name = room.name[:22]
            bar_len = int(util / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(f"│ {name:<22} │{op_count:^8}│ {bar} {util:5.1f}%      │")

        if room_stats:
            avg_util = sum(r[2] for r in room_stats) / len(room_stats)
            bar_len = int(avg_util / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append("├────────────────────────┼────────┼──────────────────────────────────────┤")
            lines.append(f"│ DURCHSCHNITT           │{'--':^8}│ {bar} {avg_util:5.1f}%      │")

        lines.append("└────────────────────────┴────────┴──────────────────────────────────────┘")

        return "\n".join(lines)

    def generate_part3(self, appointments, operations, doctors):
        """Teil 3: Konflikt-KPIs"""
        lines = []
        lines.append("╔════════════════════════════════════════════════════════════════════════╗")
        lines.append("║                    SCHEDULING KPIs (Teil 3/4)                          ║")
        lines.append("╚════════════════════════════════════════════════════════════════════════╝")
        lines.append("")

        # Konflikte zählen
        doctor_conflicts = 0
        for doc in doctors:
            doc_events = []
            for a in appointments:
                if a.doctor_id == doc.id:
                    doc_events.append((a.start_time, a.end_time))
            for o in operations:
                if o.primary_surgeon_id == doc.id:
                    doc_events.append((o.start_time, o.end_time))
            doc_events.sort()
            for i, (s1, e1) in enumerate(doc_events):
                for j, (s2, e2) in enumerate(doc_events):
                    if i < j and s1 < e2 and e1 > s2:
                        doctor_conflicts += 1

        working_hours_violations = 0
        from datetime import time
        for a in appointments:
            if a.start_time.time() < time(8, 0) or a.end_time.time() > time(17, 0):
                working_hours_violations += 1

        total_plannings = len(appointments) + len(operations)
        total_conflicts = doctor_conflicts + working_hours_violations

        lines.append("┌────────────────────────────────────────────────────────────────────────┐")
        lines.append("│  7. KONFLIKT-KPIs                                                      │")
        lines.append("├──────────────────────────────┬──────────┬────────────────────────────────┤")
        lines.append("│ Metrik                       │   Wert   │ Bewertung                      │")
        lines.append("├──────────────────────────────┼──────────┼────────────────────────────────┤")

        conf_per_100 = (total_conflicts / total_plannings * 100) if total_plannings > 0 else 0
        status = "🔴 KRITISCH" if conf_per_100 > 20 else ("🟡 WARNUNG" if conf_per_100 > 5 else "🟢 GUT")
        lines.append(f"│ Konflikte / 100 Planungen    │{conf_per_100:^10.1f}│ {status:<30}│")
        lines.append(f"│ Arzt-Doppelbelegungen        │{doctor_conflicts:^10}│ {'🔴 ' + str(doctor_conflicts) + ' Konflikte' if doctor_conflicts else '🟢 OK':<30}│")
        lines.append(f"│ Arbeitszeit-Verstöße         │{working_hours_violations:^10}│ {'🟡 ' + str(working_hours_violations) + ' außerhalb' if working_hours_violations else '🟢 OK':<30}│")
        lines.append(f"│ Gesamt-Konflikte             │{total_conflicts:^10}│                                │")

        lines.append("└──────────────────────────────┴──────────┴────────────────────────────────┘")
        lines.append("")

        # Effizienz
        efficiency = max(0, 100 - conf_per_100 * 2)
        lines.append("┌────────────────────────────────────────────────────────────────────────┐")
        lines.append("│  8. SCHEDULING-EFFIZIENZ                                               │")
        lines.append("├──────────────────────────────────────────────────────────────────────────┤")
        bar_len = int(efficiency / 2.5)
        bar = "█" * bar_len + "░" * (40 - bar_len)
        status = "🟢 OPTIMAL" if efficiency >= 80 else ("🟡 VERBESSERBAR" if efficiency >= 50 else "🔴 KRITISCH")
        lines.append(f"│  Effizienz: {bar} {efficiency:5.1f}% {status}  │")
        lines.append("└────────────────────────────────────────────────────────────────────────┘")

        return "\n".join(lines)

    def generate_part4(self, appointments, operations):
        """Teil 4: Zusammenfassung & Empfehlungen"""
        lines = []
        lines.append("╔════════════════════════════════════════════════════════════════════════╗")
        lines.append("║                    SCHEDULING KPIs (Teil 4/4)                          ║")
        lines.append("╚════════════════════════════════════════════════════════════════════════╝")
        lines.append("")

        apt_durations = [(a.end_time - a.start_time).total_seconds() / 60 for a in appointments if a.end_time and a.start_time]
        op_durations = [(o.end_time - o.start_time).total_seconds() / 60 for o in operations if o.end_time and o.start_time]

        lines.append("┌────────────────────────────────────────────────────────────────────────┐")
        lines.append("│  9. KPI-ZUSAMMENFASSUNG                                                │")
        lines.append("├────────────────────────────────┬─────────────────────────────────────────┤")

        lines.append(f"│ Gesamtzahl Termine             │ {len(appointments):<39}│")
        lines.append(f"│ Gesamtzahl Operationen         │ {len(operations):<39}│")
        if apt_durations:
            lines.append(f"│ Ø Terminlänge                  │ {mean(apt_durations):.1f} min{' ' * 32}│")
        if op_durations:
            lines.append(f"│ Ø OP-Dauer                     │ {mean(op_durations):.1f} min{' ' * 31}│")

        lines.append("└────────────────────────────────┴─────────────────────────────────────────┘")
        lines.append("")

        lines.append("┌────────────────────────────────────────────────────────────────────────┐")
        lines.append("│  10. EMPFEHLUNGEN                                                      │")
        lines.append("├────────────────────────────────────────────────────────────────────────┤")
        lines.append("│ 1. Peak-Stunden entlasten (Termine auf Randzeiten verteilen)          │")
        lines.append("│ 2. Arzt-Auslastung gleichmäßiger verteilen                            │")
        lines.append("│ 3. OP-Räume besser auslasten (freie Kapazitäten nutzen)               │")
        lines.append("│ 4. Arbeitszeit-Verstöße vermeiden (Termine vor 17:00)                 │")
        lines.append("│ 5. Konflikt-Rate unter 5% halten                                      │")
        lines.append("└────────────────────────────────────────────────────────────────────────┘")

        return "\n".join(lines)
