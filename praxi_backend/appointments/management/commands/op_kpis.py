"""Management command to calculate OP KPIs (Teil 2/5)"""
from django.core.management.base import BaseCommand
from datetime import datetime, timedelta
from collections import defaultdict
from praxi_backend.appointments.models import Operation, Resource


class Command(BaseCommand):
    help = 'Calculate OP KPIs (Teil 2/5)'

    def handle(self, *args, **options):
        ops = list(Operation.objects.using('default').select_related('op_room', 'primary_surgeon').all())
        rooms = list(Resource.objects.using('default').filter(type='room').all())

        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        self.stdout.write('=' * 70)
        self.stdout.write('                    OP-KPIs (Teil 2/5)')
        self.stdout.write('=' * 70)
        self.stdout.write('')

        # 1. MENGEN
        ops_today = [o for o in ops if o.start_time and o.start_time.date() == today]
        ops_week = [o for o in ops if o.start_time and o.start_time.date() >= week_start]
        ops_month = [o for o in ops if o.start_time and o.start_time.date() >= month_start]

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 1. MENGEN-UEBERSICHT' + ' ' * 47 + '|')
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 11 + '+' + '-' * 11 + '+' + '-' * 11 + '+' + '-' * 11 + '+')
        self.stdout.write('| Metrik             |    Tag    |   Woche   |   Monat   |  Gesamt   |')
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 11 + '+' + '-' * 11 + '+' + '-' * 11 + '+' + '-' * 11 + '+')
        self.stdout.write(f'| Operationen        |{len(ops_today):^11}|{len(ops_week):^11}|{len(ops_month):^11}|{len(ops):^11}|')
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 11 + '+' + '-' * 11 + '+' + '-' * 11 + '+' + '-' * 11 + '+')
        self.stdout.write('')

        # 2. DAUER
        durations = [(op.end_time - op.start_time).total_seconds() / 60 
                     for op in ops if op.start_time and op.end_time]
        if durations:
            avg_dur = sum(durations) / len(durations)
            sorted_dur = sorted(durations)
            n = len(sorted_dur)
            median_dur = sorted_dur[n // 2] if n % 2 == 1 else (sorted_dur[n//2-1] + sorted_dur[n//2]) / 2
            min_dur, max_dur = min(durations), max(durations)
        else:
            avg_dur = median_dur = min_dur = max_dur = 0

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 2. DAUER-STATISTIKEN (Minuten)' + ' ' * 36 + '|')
        self.stdout.write('+' + '-' * 25 + '+' + '-' * 14 + '+' + '-' * 26 + '+')
        self.stdout.write('| Metrik                  |     Wert     | Visualisierung             |')
        self.stdout.write('+' + '-' * 25 + '+' + '-' * 14 + '+' + '-' * 26 + '+')
        max_bar = max_dur if max_dur > 0 else 1
        self.stdout.write(f'| Durchschnitt            |{avg_dur:>10.1f} min| {"#" * int(avg_dur / max_bar * 20):<25}|')
        self.stdout.write(f'| Median                  |{median_dur:>10.1f} min| {"#" * int(median_dur / max_bar * 20):<25}|')
        self.stdout.write(f'| Minimum                 |{min_dur:>10.1f} min| {"#" * int(min_dur / max_bar * 20):<25}|')
        self.stdout.write(f'| Maximum                 |{max_dur:>10.1f} min| {"#" * 20:<25}|')
        self.stdout.write('+' + '-' * 25 + '+' + '-' * 14 + '+' + '-' * 26 + '+')
        self.stdout.write('')

        # 3. SAAL-AUSLASTUNG
        WORK_MINUTES, work_days = 540, 22
        room_minutes = defaultdict(float)
        for op in ops:
            if op.start_time and op.end_time and op.op_room:
                room_minutes[op.op_room.name] += (op.end_time - op.start_time).total_seconds() / 60

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 3. OP-SAAL-AUSLASTUNG' + ' ' * 46 + '|')
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 25 + '+')
        self.stdout.write('| OP-Saal            | OP-Min   | Ausl. %  | Visualisierung          |')
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 25 + '+')
        total_capacity = WORK_MINUTES * work_days
        room_utils = [(r.name, room_minutes.get(r.name, 0), room_minutes.get(r.name, 0) / total_capacity * 100) for r in rooms]
        room_utils.sort(key=lambda x: -x[2])
        max_util = max(u[2] for u in room_utils) if room_utils else 1

        for name, mins, util in room_utils:
            bar = '#' * int(util / max(max_util, 1) * 20)
            peak = ' <- PEAK' if util == max_util and util > 0 else ''
            self.stdout.write(f'| {name:<18} |{mins:>8.0f}  |{util:>8.1f}% | {bar:<16}{peak:>8}|')

        if room_utils:
            avg_util = sum(u[2] for u in room_utils) / len(room_utils)
            self.stdout.write('+' + '-' * 20 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 25 + '+')
            self.stdout.write(f'| Durchschnitt       |          |{avg_util:>8.1f}% | {"~" * int(avg_util / max(max_util, 1) * 20):<24}|')
        self.stdout.write('+' + '-' * 20 + '+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 25 + '+')
        self.stdout.write('')

        # 4. PEAK-STUNDEN
        hour_counts = defaultdict(int)
        for op in ops:
            if op.start_time:
                hour_counts[op.start_time.hour] += 1

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 4. PEAK-STUNDEN (OP-Starts)' + ' ' * 40 + '|')
        self.stdout.write('+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 45 + '+')
        self.stdout.write('|  Stunde  |  Anzahl  | Verteilung                                  |')
        self.stdout.write('+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 45 + '+')
        sorted_hours = sorted(hour_counts.items(), key=lambda x: -x[1])[:6]
        max_h = max(c for _, c in sorted_hours) if sorted_hours else 1
        for h, c in sorted_hours:
            peak = ' <- PEAK' if c == max_h else ''
            self.stdout.write(f'|  {h:02d}:00   |{c:^10}| {"#" * int(c / max_h * 35):<36}{peak:>8}|')
        self.stdout.write('+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 45 + '+')
        self.stdout.write('')

        # 5. PEAK-TAGE
        day_names = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
        day_counts = defaultdict(int)
        for op in ops:
            if op.start_time:
                day_counts[op.start_time.weekday()] += 1

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 5. PEAK-TAGE' + ' ' * 55 + '|')
        self.stdout.write('+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 45 + '+')
        self.stdout.write('|   Tag    |  Anzahl  | Verteilung                                  |')
        self.stdout.write('+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 45 + '+')
        sorted_days = sorted(day_counts.items(), key=lambda x: -x[1])
        max_d = max(c for _, c in sorted_days) if sorted_days else 1
        for d, c in sorted_days:
            peak = ' <- PEAK' if c == max_d else ''
            self.stdout.write(f'|    {day_names[d]:<5} |{c:^10}| {"#" * int(c / max_d * 35):<36}{peak:>8}|')
        self.stdout.write('+' + '-' * 10 + '+' + '-' * 10 + '+' + '-' * 45 + '+')
        self.stdout.write('')

        # 6. OP-DICHTE PRO ARZT
        surgeon_ops = defaultdict(list)
        for op in ops:
            if op.primary_surgeon:
                surgeon_ops[op.primary_surgeon.username].append(op)

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 6. OP-DICHTE PRO ARZT' + ' ' * 46 + '|')
        self.stdout.write('+' + '-' * 18 + '+' + '-' * 8 + '+' + '-' * 12 + '+' + '-' * 27 + '+')
        self.stdout.write('| Chirurg          | Anzahl | Dauer      | Visualisierung            |')
        self.stdout.write('+' + '-' * 18 + '+' + '-' * 8 + '+' + '-' * 12 + '+' + '-' * 27 + '+')
        surgeon_stats = []
        for s, ol in surgeon_ops.items():
            count = len(ol)
            durs = [(o.end_time - o.start_time).total_seconds() / 60 for o in ol if o.end_time and o.start_time]
            avg = sum(durs) / len(durs) if durs else 0
            surgeon_stats.append((s, count, avg))
        surgeon_stats.sort(key=lambda x: -x[1])
        max_s = max(s[1] for s in surgeon_stats) if surgeon_stats else 1
        for s, c, a in surgeon_stats[:6]:
            peak = ' <- TOP' if c == max_s else ''
            self.stdout.write(f'| {s:<16} |{c:^8}|{a:>8.1f} min| {"#" * int(c / max_s * 20):<19}{peak:>7}|')
        self.stdout.write('+' + '-' * 18 + '+' + '-' * 8 + '+' + '-' * 12 + '+' + '-' * 27 + '+')
        self.stdout.write('')

        # 7. OP-DICHTE PRO RAUM
        room_ops = defaultdict(list)
        for op in ops:
            if op.op_room:
                room_ops[op.op_room.name].append(op)

        self.stdout.write('+' + '-' * 68 + '+')
        self.stdout.write('| 7. OP-DICHTE PRO RAUM' + ' ' * 46 + '|')
        self.stdout.write('+' + '-' * 18 + '+' + '-' * 8 + '+' + '-' * 12 + '+' + '-' * 27 + '+')
        self.stdout.write('| OP-Saal          | Anzahl | Dauer      | Visualisierung            |')
        self.stdout.write('+' + '-' * 18 + '+' + '-' * 8 + '+' + '-' * 12 + '+' + '-' * 27 + '+')
        room_stats = []
        for r, ol in room_ops.items():
            count = len(ol)
            durs = [(o.end_time - o.start_time).total_seconds() / 60 for o in ol if o.end_time and o.start_time]
            avg = sum(durs) / len(durs) if durs else 0
            room_stats.append((r, count, avg))
        room_stats.sort(key=lambda x: -x[1])
        max_r = max(s[1] for s in room_stats) if room_stats else 1
        for r, c, a in room_stats:
            peak = ' <- TOP' if c == max_r else ''
            self.stdout.write(f'| {r:<16} |{c:^8}|{a:>8.1f} min| {"#" * int(c / max_r * 20):<19}{peak:>7}|')
        self.stdout.write('+' + '-' * 18 + '+' + '-' * 8 + '+' + '-' * 12 + '+' + '-' * 27 + '+')
        self.stdout.write('')

        # ZUSAMMENFASSUNG
        self.stdout.write('=' * 70)
        self.stdout.write('                    ZUSAMMENFASSUNG')
        self.stdout.write('=' * 70)
        self.stdout.write(f'  * Gesamt-OPs:           {len(ops)}')
        self.stdout.write(f'  * Durchschnittl. Dauer: {avg_dur:.1f} min')
        self.stdout.write(f'  * Median OP-Dauer:      {median_dur:.1f} min')
        if room_utils:
            self.stdout.write(f'  * Durchschnittl. Saal-Ausl.: {avg_util:.1f}%')
        if sorted_hours:
            self.stdout.write(f'  * Peak-Stunde:          {sorted_hours[0][0]:02d}:00 ({sorted_hours[0][1]} OPs)')
        if sorted_days:
            self.stdout.write(f'  * Peak-Tag:             {day_names[sorted_days[0][0]]} ({sorted_days[0][1]} OPs)')
        if surgeon_stats:
            self.stdout.write(f'  * Top-Chirurg:          {surgeon_stats[0][0]} ({surgeon_stats[0][1]} OPs)')
        self.stdout.write('=' * 70)
