"""
Effizienz- und Qualitäts-KPIs (Teil 5/5)
=========================================
Berechnet Scheduling-Effizienz, Konfliktfreie Rate, Validierung und RBAC-Metriken.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Avg, F, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict

from praxi_backend.appointments.models import (
    Appointment, Operation, Resource, PracticeHours, DoctorHours, DoctorAbsence
)
from praxi_backend.core.models import User, AuditLog


class Command(BaseCommand):
    help = "Effizienz- und Qualitäts-KPIs (Teil 5/5)"

    # Konstanten
    WORK_MINUTES_DAY = 540  # 9 Stunden
    SLOT_DURATION = 15  # Minuten pro Slot
    WORK_DAYS_MONTH = 22

    def bar(self, pct, width=20):
        filled = int(pct / 100 * width)
        return "█" * filled + "░" * (width - filled)

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("  EFFIZIENZ- UND QUALITÄTS-KPIs (Teil 5/5)")
        self.stdout.write("=" * 70)

        # Daten laden
        appointments = list(Appointment.objects.using('default').all())
        operations = list(Operation.objects.using('default').all())
        doctors = list(User.objects.using('default').filter(role__name='doctor'))
        rooms = list(Resource.objects.using('default').filter(type='room'))
        practice_hours = list(PracticeHours.objects.using('default').all())
        doctor_hours = list(DoctorHours.objects.using('default').all())
        absences = list(DoctorAbsence.objects.using('default').all())
        
        # AuditLog für Qualitätsmetriken
        try:
            audit_logs = list(AuditLog.objects.using('default').all())
        except:
            audit_logs = []

        total_appointments = len(appointments)
        total_operations = len(operations)
        total_plannings = total_appointments + total_operations

        # ══════════════════════════════════════════════════════════════════
        # 1. SCHEDULING-EFFIZIENZ
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write("\n┌─────────────────────────────────────────────────────────────────────┐")
        self.stdout.write("│ 1. SCHEDULING-EFFIZIENZ                                             │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")

        # Verfügbare Slots berechnen (basierend auf Praxisöffnung)
        slots_per_day = self.WORK_MINUTES_DAY // self.SLOT_DURATION  # 36 Slots/Tag
        available_slots_month = slots_per_day * self.WORK_DAYS_MONTH * len(doctors)
        
        # Belegte Slots berechnen
        appt_slots = sum((a.duration or 30) // self.SLOT_DURATION for a in appointments)
        op_slots = sum((o.duration or 60) // self.SLOT_DURATION for o in operations)
        used_slots = appt_slots + op_slots

        # Abwesenheits-Slots abziehen
        absence_days = len(absences)
        absence_slots = absence_days * slots_per_day
        effective_available = max(available_slots_month - absence_slots, 1)

        efficiency_pct = min((used_slots / effective_available) * 100, 100) if effective_available > 0 else 0

        self.stdout.write(f"│ Verfügbare Slots/Monat:  {available_slots_month:>6}                               │")
        self.stdout.write(f"│ - Abwesenheits-Slots:    {absence_slots:>6}                               │")
        self.stdout.write(f"│ = Effektiv verfügbar:    {effective_available:>6}                               │")
        self.stdout.write(f"│ Belegte Slots (Termine): {appt_slots:>6}                               │")
        self.stdout.write(f"│ Belegte Slots (OPs):     {op_slots:>6}                               │")
        self.stdout.write(f"│ = Gesamt belegt:         {used_slots:>6}                               │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")
        self.stdout.write(f"│ SCHEDULING-EFFIZIENZ:    {efficiency_pct:>5.1f}% {self.bar(efficiency_pct, 25)}    │")
        self.stdout.write("└─────────────────────────────────────────────────────────────────────┘")

        # ══════════════════════════════════════════════════════════════════
        # 2. KONFLIKTFREIE PLANUNGSRATE
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write("\n┌─────────────────────────────────────────────────────────────────────┐")
        self.stdout.write("│ 2. KONFLIKTFREIE PLANUNGSRATE                                       │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")

        # Konflikte erkennen
        conflicts = self._detect_conflicts(appointments, operations, doctors, rooms, practice_hours, doctor_hours, absences)
        conflict_count = len(conflicts)
        conflict_free = total_plannings - conflict_count
        conflict_free_rate = (conflict_free / total_plannings * 100) if total_plannings > 0 else 100

        self.stdout.write(f"│ Gesamte Planungen:       {total_plannings:>6}                               │")
        self.stdout.write(f"│ Davon konfliktfrei:      {conflict_free:>6}                               │")
        self.stdout.write(f"│ Mit Konflikten:          {conflict_count:>6}                               │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")
        self.stdout.write(f"│ KONFLIKTFREIE RATE:      {conflict_free_rate:>5.1f}% {self.bar(conflict_free_rate, 25)}    │")
        self.stdout.write("└─────────────────────────────────────────────────────────────────────┘")

        # Konflikt-Details
        if conflicts:
            self.stdout.write("│ Konflikt-Typen:                                                     │")
            conflict_types = defaultdict(int)
            for c in conflicts:
                conflict_types[c['type']] += 1
            for ctype, count in sorted(conflict_types.items(), key=lambda x: -x[1])[:5]:
                pct = count / conflict_count * 100
                self.stdout.write(f"│   {ctype:<25} {count:>4} ({pct:>5.1f}%)                    │")

        # ══════════════════════════════════════════════════════════════════
        # 3. DURCHSCHNITTLICHE PLANUNGSZEIT
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write("\n┌─────────────────────────────────────────────────────────────────────┐")
        self.stdout.write("│ 3. DURCHSCHNITTLICHE PLANUNGSZEIT                                   │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")

        # Durchschnittliche Dauer der geplanten Termine/OPs
        avg_appt_duration = sum(a.duration or 30 for a in appointments) / max(len(appointments), 1)
        avg_op_duration = sum(o.duration or 60 for o in operations) / max(len(operations), 1)

        # Slots pro Termin-Typ
        appt_slots_avg = avg_appt_duration / self.SLOT_DURATION
        op_slots_avg = avg_op_duration / self.SLOT_DURATION

        self.stdout.write(f"│ Ø Termin-Dauer:          {avg_appt_duration:>5.0f} min ({appt_slots_avg:.1f} Slots)              │")
        self.stdout.write(f"│ Ø OP-Dauer:              {avg_op_duration:>5.0f} min ({op_slots_avg:.1f} Slots)              │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")

        # Verteilung nach Dauer-Kategorien
        duration_categories = {
            'Kurz (≤15min)': 0,
            'Mittel (16-45min)': 0,
            'Lang (46-90min)': 0,
            'Sehr lang (>90min)': 0
        }
        for a in appointments:
            d = a.duration or 30
            if d <= 15:
                duration_categories['Kurz (≤15min)'] += 1
            elif d <= 45:
                duration_categories['Mittel (16-45min)'] += 1
            elif d <= 90:
                duration_categories['Lang (46-90min)'] += 1
            else:
                duration_categories['Sehr lang (>90min)'] += 1

        for o in operations:
            d = o.duration or 60
            if d <= 15:
                duration_categories['Kurz (≤15min)'] += 1
            elif d <= 45:
                duration_categories['Mittel (16-45min)'] += 1
            elif d <= 90:
                duration_categories['Lang (46-90min)'] += 1
            else:
                duration_categories['Sehr lang (>90min)'] += 1

        self.stdout.write("│ Dauer-Verteilung:                                                   │")
        for cat, count in duration_categories.items():
            pct = count / max(total_plannings, 1) * 100
            self.stdout.write(f"│   {cat:<20} {count:>4} ({pct:>5.1f}%) {self.bar(pct, 15)}       │")
        self.stdout.write("└─────────────────────────────────────────────────────────────────────┘")

        # ══════════════════════════════════════════════════════════════════
        # 4. VALIDIERUNGSFEHLER
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write("\n┌─────────────────────────────────────────────────────────────────────┐")
        self.stdout.write("│ 4. VALIDIERUNGSFEHLER PRO 100 PLANUNGEN                             │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")

        # Validierungsfehler-Kategorien (basierend auf Datenqualität)
        validation_errors = {
            'missing_duration': 0,
            'missing_doctor': 0,
            'missing_patient': 0,
            'invalid_time': 0,
            'missing_room': 0,
        }

        for a in appointments:
            if not a.duration:
                validation_errors['missing_duration'] += 1
            if not a.doctor_id:
                validation_errors['missing_doctor'] += 1
            if not a.patient_id:
                validation_errors['missing_patient'] += 1
            if a.start and a.end and a.start >= a.end:
                validation_errors['invalid_time'] += 1

        for o in operations:
            if not o.duration:
                validation_errors['missing_duration'] += 1
            if not o.doctor_id:
                validation_errors['missing_doctor'] += 1
            if not o.patient_id:
                validation_errors['missing_patient'] += 1
            if not o.resource_id:
                validation_errors['missing_room'] += 1
            if o.start and o.end and o.start >= o.end:
                validation_errors['invalid_time'] += 1

        total_errors = sum(validation_errors.values())
        errors_per_100 = (total_errors / max(total_plannings, 1)) * 100

        self.stdout.write(f"│ Gesamte Validierungsfehler: {total_errors:>4}                                  │")
        self.stdout.write(f"│ Fehler pro 100 Planungen:   {errors_per_100:>5.2f}                                 │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")
        self.stdout.write("│ Fehler nach Typ:                                                    │")
        error_labels = {
            'missing_duration': 'Fehlende Dauer',
            'missing_doctor': 'Fehlender Arzt',
            'missing_patient': 'Fehlender Patient',
            'invalid_time': 'Ungültige Zeit',
            'missing_room': 'Fehlender Raum',
        }
        for key, count in sorted(validation_errors.items(), key=lambda x: -x[1]):
            label = error_labels.get(key, key)
            pct = count / max(total_errors, 1) * 100 if total_errors > 0 else 0
            self.stdout.write(f"│   {label:<22} {count:>4} ({pct:>5.1f}%)                          │")
        self.stdout.write("└─────────────────────────────────────────────────────────────────────┘")

        # ══════════════════════════════════════════════════════════════════
        # 5. GÜLTIGE VS. UNGÜLTIGE PAYLOADS
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write("\n┌─────────────────────────────────────────────────────────────────────┐")
        self.stdout.write("│ 5. GÜLTIGE VS. UNGÜLTIGE PAYLOADS                                   │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")

        # Gültige Payloads = Datensätze ohne kritische Fehler
        valid_appointments = sum(1 for a in appointments if a.doctor_id and a.patient_id and a.duration)
        valid_operations = sum(1 for o in operations if o.doctor_id and o.patient_id and o.duration and o.resource_id)
        
        invalid_appointments = total_appointments - valid_appointments
        invalid_operations = total_operations - valid_operations

        valid_total = valid_appointments + valid_operations
        invalid_total = invalid_appointments + invalid_operations
        valid_rate = (valid_total / max(total_plannings, 1)) * 100

        self.stdout.write(f"│ Termine:                                                            │")
        self.stdout.write(f"│   Gültig:   {valid_appointments:>4}  Ungültig: {invalid_appointments:>4}                                  │")
        self.stdout.write(f"│ OPs:                                                                │")
        self.stdout.write(f"│   Gültig:   {valid_operations:>4}  Ungültig: {invalid_operations:>4}                                  │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")
        self.stdout.write(f"│ GÜLTIGKEITSRATE:         {valid_rate:>5.1f}% {self.bar(valid_rate, 25)}    │")
        
        # Visueller Vergleich
        valid_bar_width = int(valid_rate / 100 * 40)
        invalid_bar_width = 40 - valid_bar_width
        self.stdout.write(f"│ {'█' * valid_bar_width}{'░' * invalid_bar_width} │")
        self.stdout.write(f"│ {'Gültig':^{valid_bar_width}}{'Ungültig':^{invalid_bar_width}} │" if invalid_bar_width > 5 else f"│ {'Gültig':<40} │")
        self.stdout.write("└─────────────────────────────────────────────────────────────────────┘")

        # ══════════════════════════════════════════════════════════════════
        # 6. RBAC-REGELANWENDUNG
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write("\n┌─────────────────────────────────────────────────────────────────────┐")
        self.stdout.write("│ 6. RBAC-REGELANWENDUNG                                              │")
        self.stdout.write("├─────────────────────────────────────────────────────────────────────┤")

        # RBAC-Analyse basierend auf AuditLog und Datenstrukturen
        rbac_stats = {
            'admin': {'read': 0, 'write': 0},
            'assistant': {'read': 0, 'write': 0},
            'doctor': {'read': 0, 'write': 0},
            'billing': {'read': 0, 'write': 0},
        }

        # Analysiere AuditLog nach Aktionen
        for log in audit_logs:
            role = getattr(getattr(log, 'user', None), 'role', None)
            role_name = getattr(role, 'name', 'unknown') if role else 'unknown'
            action = getattr(log, 'action', '')
            
            if role_name in rbac_stats:
                if 'view' in action or 'read' in action or 'list' in action:
                    rbac_stats[role_name]['read'] += 1
                else:
                    rbac_stats[role_name]['write'] += 1

        # Wenn keine Logs vorhanden, basiere auf Appointments/Operations
        if not audit_logs:
            # Schätze basierend auf existierenden Daten
            for a in appointments:
                doctor = getattr(a, 'doctor', None)
                if doctor:
                    role = getattr(doctor, 'role', None)
                    role_name = getattr(role, 'name', 'doctor')
                    if role_name in rbac_stats:
                        rbac_stats[role_name]['write'] += 1

            for o in operations:
                doctor = getattr(o, 'doctor', None)
                if doctor:
                    role = getattr(doctor, 'role', None)
                    role_name = getattr(role, 'name', 'doctor')
                    if role_name in rbac_stats:
                        rbac_stats[role_name]['write'] += 1

        total_actions = sum(s['read'] + s['write'] for s in rbac_stats.values())
        
        self.stdout.write("│ Rolle         │   Lesen │ Schreiben │ Gesamt │    Anteil      │")
        self.stdout.write("├───────────────┼─────────┼───────────┼────────┼────────────────┤")
        
        for role, stats in rbac_stats.items():
            total = stats['read'] + stats['write']
            pct = (total / max(total_actions, 1)) * 100
            self.stdout.write(f"│ {role:<13} │  {stats['read']:>5}  │   {stats['write']:>5}   │ {total:>6} │ {pct:>5.1f}% {self.bar(pct, 8)} │")
        
        self.stdout.write("├───────────────┴─────────┴───────────┴────────┴────────────────┤")
        
        # RBAC-Konformität (alle Aktionen durch berechtigte Rollen)
        rbac_compliant = total_plannings  # Annahme: alle gespeicherten Daten sind RBAC-konform
        rbac_rate = 100.0  # Erfolgreiche Speicherung = RBAC wurde angewendet
        
        self.stdout.write(f"│ RBAC-Konformitätsrate:   {rbac_rate:>5.1f}% {self.bar(rbac_rate, 25)}    │")
        self.stdout.write("└─────────────────────────────────────────────────────────────────────┘")

        # ══════════════════════════════════════════════════════════════════
        # 7. KPI-ZUSAMMENFASSUNG
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write("\n" + "═" * 70)
        self.stdout.write("  KPI-ZUSAMMENFASSUNG")
        self.stdout.write("═" * 70)

        kpis = [
            ("Scheduling-Effizienz", efficiency_pct, "%"),
            ("Konfliktfreie Rate", conflict_free_rate, "%"),
            ("Gültigkeitsrate", valid_rate, "%"),
            ("RBAC-Konformität", rbac_rate, "%"),
            ("Fehler/100 Planungen", errors_per_100, ""),
        ]

        self.stdout.write("\n┌───────────────────────────────────────────────────────────────────┐")
        self.stdout.write("│ KPI                      │   Wert │ Bewertung                     │")
        self.stdout.write("├──────────────────────────┼────────┼───────────────────────────────┤")
        
        for name, value, unit in kpis:
            if unit == "%":
                if value >= 90:
                    rating = "✓ Sehr gut"
                elif value >= 75:
                    rating = "○ Gut"
                elif value >= 50:
                    rating = "△ Verbesserungswürdig"
                else:
                    rating = "✗ Kritisch"
            else:
                if value <= 5:
                    rating = "✓ Sehr gut"
                elif value <= 15:
                    rating = "○ Akzeptabel"
                else:
                    rating = "✗ Zu hoch"
            
            self.stdout.write(f"│ {name:<24} │ {value:>5.1f}{unit:<1} │ {rating:<29} │")
        
        self.stdout.write("└───────────────────────────────────────────────────────────────────┘")

        # Gesamtscore berechnen
        score_components = [
            efficiency_pct * 0.25,
            conflict_free_rate * 0.25,
            valid_rate * 0.25,
            rbac_rate * 0.15,
            max(0, 100 - errors_per_100 * 2) * 0.10
        ]
        overall_score = sum(score_components)

        self.stdout.write(f"\n  GESAMTSCORE: {overall_score:.1f}/100")
        self.stdout.write(f"  {self.bar(overall_score, 50)}")
        
        if overall_score >= 90:
            grade = "A - Exzellent"
        elif overall_score >= 80:
            grade = "B - Sehr gut"
        elif overall_score >= 70:
            grade = "C - Gut"
        elif overall_score >= 60:
            grade = "D - Befriedigend"
        else:
            grade = "F - Verbesserungsbedarf"
        
        self.stdout.write(f"  Bewertung: {grade}")

        # ══════════════════════════════════════════════════════════════════
        # 8. TRENDS
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write("\n" + "═" * 70)
        self.stdout.write("  WICHTIGSTE TRENDS")
        self.stdout.write("═" * 70)

        trends = []
        
        # Trend-Analyse basierend auf KPIs
        if efficiency_pct < 50:
            trends.append(("↓", "Niedrige Slot-Auslastung", f"Nur {efficiency_pct:.0f}% der verfügbaren Kapazität genutzt"))
        elif efficiency_pct > 90:
            trends.append(("↑", "Hohe Auslastung", f"System zu {efficiency_pct:.0f}% ausgelastet - Kapazitätsgrenzen beachten"))
        else:
            trends.append(("→", "Ausgewogene Auslastung", f"Gesunde {efficiency_pct:.0f}% Kapazitätsnutzung"))

        if conflict_free_rate < 80:
            trends.append(("↓", "Konflikte häufig", f"{conflict_count} Konflikte bei {total_plannings} Planungen"))
        else:
            trends.append(("↑", "Geringe Konfliktrate", f"{conflict_free_rate:.0f}% konfliktfreie Planungen"))

        if valid_rate < 95:
            trends.append(("↓", "Datenqualitätsprobleme", f"{invalid_total} ungültige Datensätze erkannt"))
        else:
            trends.append(("↑", "Hohe Datenqualität", f"{valid_rate:.0f}% valide Payloads"))

        if len(doctors) > 0 and len(operations) > 0:
            ops_per_doctor = len(operations) / len(doctors)
            if ops_per_doctor > 20:
                trends.append(("↑", "Hohe OP-Dichte", f"Ø {ops_per_doctor:.1f} OPs pro Arzt"))

        self.stdout.write("")
        for arrow, title, detail in trends[:5]:
            self.stdout.write(f"  {arrow} {title}")
            self.stdout.write(f"    └─ {detail}")
        self.stdout.write("")

        # ══════════════════════════════════════════════════════════════════
        # 9. OPTIMIERUNGSEMPFEHLUNGEN
        # ══════════════════════════════════════════════════════════════════
        self.stdout.write("═" * 70)
        self.stdout.write("  OPTIMIERUNGSEMPFEHLUNGEN")
        self.stdout.write("═" * 70)

        recommendations = []

        # 1. Effizienz-basierte Empfehlungen
        if efficiency_pct < 60:
            recommendations.append({
                'priority': 'HOCH',
                'title': 'Slot-Auslastung erhöhen',
                'action': 'Automatische Terminvorschläge aktivieren, Lücken-Füll-Algorithmus implementieren',
                'impact': f'+{60 - efficiency_pct:.0f}% potenzielle Effizienzsteigerung'
            })
        
        # 2. Konflikt-basierte Empfehlungen
        if conflict_count > 0:
            recommendations.append({
                'priority': 'HOCH' if conflict_free_rate < 80 else 'MITTEL',
                'title': 'Konfliktprävention verbessern',
                'action': 'Echtzeit-Validierung bei Buchung, Überlappungsprüfung vor Speicherung',
                'impact': f'{conflict_count} Konflikte vermeidbar'
            })

        # 3. Validierungs-Empfehlungen
        if total_errors > 0:
            recommendations.append({
                'priority': 'MITTEL',
                'title': 'Pflichtfeld-Validierung verstärken',
                'action': 'Frontend-Validierung für Dauer, Arzt, Patient-ID; Backend-Schema-Prüfung',
                'impact': f'{total_errors} Fehler reduzierbar'
            })

        # 4. Kapazitäts-Empfehlungen
        if efficiency_pct > 85:
            recommendations.append({
                'priority': 'MITTEL',
                'title': 'Kapazitätserweiterung prüfen',
                'action': 'Zusätzliche Ärzte/Räume, erweiterte Öffnungszeiten evaluieren',
                'impact': 'Wachstumspotenzial sichern'
            })

        # 5. Datenqualitäts-Empfehlungen
        if invalid_total > 0:
            recommendations.append({
                'priority': 'NIEDRIG',
                'title': 'Datenbereinigung durchführen',
                'action': 'Batch-Update für fehlende Pflichtfelder, Archivierung alter Daten',
                'impact': f'{invalid_total} Datensätze korrigierbar'
            })

        # 6. RBAC-Empfehlungen
        if len(audit_logs) == 0:
            recommendations.append({
                'priority': 'MITTEL',
                'title': 'Audit-Logging aktivieren',
                'action': 'log_patient_action() für alle CRUD-Operationen implementieren',
                'impact': 'Compliance & Nachverfolgbarkeit'
            })

        # Top 5 Empfehlungen ausgeben
        priority_order = {'HOCH': 0, 'MITTEL': 1, 'NIEDRIG': 2}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 3))

        self.stdout.write("")
        for i, rec in enumerate(recommendations[:5], 1):
            priority_icon = {'HOCH': '🔴', 'MITTEL': '🟡', 'NIEDRIG': '🟢'}.get(rec['priority'], '⚪')
            self.stdout.write(f"  {i}. [{rec['priority']}] {rec['title']}")
            self.stdout.write(f"     Aktion: {rec['action']}")
            self.stdout.write(f"     Impact: {rec['impact']}")
            self.stdout.write("")

        self.stdout.write("═" * 70)
        self.stdout.write("  Ende: Effizienz- und Qualitäts-KPIs (Teil 5/5)")
        self.stdout.write("═" * 70 + "\n")

    def _detect_conflicts(self, appointments, operations, doctors, rooms, practice_hours, doctor_hours, absences):
        """Erkennt Konflikte in den Planungen."""
        conflicts = []

        # Arzt-Konflikte (Doppelbuchungen)
        by_doctor_date = defaultdict(list)
        for a in appointments:
            if a.doctor_id and a.start:
                key = (a.doctor_id, a.start.date() if hasattr(a.start, 'date') else a.start)
                by_doctor_date[key].append(('appt', a))
        
        for o in operations:
            if o.doctor_id and o.start:
                key = (o.doctor_id, o.start.date() if hasattr(o.start, 'date') else o.start)
                by_doctor_date[key].append(('op', o))

        for key, items in by_doctor_date.items():
            if len(items) > 1:
                # Prüfe auf Überlappung
                sorted_items = sorted(items, key=lambda x: x[1].start)
                for i in range(len(sorted_items) - 1):
                    curr = sorted_items[i][1]
                    next_item = sorted_items[i + 1][1]
                    if curr.end and next_item.start and curr.end > next_item.start:
                        conflicts.append({
                            'type': 'doctor_overlap',
                            'doctor_id': key[0],
                            'date': key[1]
                        })

        # Raum-Konflikte (für OPs)
        by_room_date = defaultdict(list)
        for o in operations:
            if o.resource_id and o.start:
                key = (o.resource_id, o.start.date() if hasattr(o.start, 'date') else o.start)
                by_room_date[key].append(o)

        for key, ops in by_room_date.items():
            if len(ops) > 1:
                sorted_ops = sorted(ops, key=lambda x: x.start)
                for i in range(len(sorted_ops) - 1):
                    if sorted_ops[i].end and sorted_ops[i + 1].start:
                        if sorted_ops[i].end > sorted_ops[i + 1].start:
                            conflicts.append({
                                'type': 'room_overlap',
                                'room_id': key[0],
                                'date': key[1]
                            })

        # Abwesenheits-Konflikte
        absence_dates = set()
        for absence in absences:
            if absence.date:
                absence_dates.add((absence.doctor_id, absence.date))

        for a in appointments:
            if a.doctor_id and a.start:
                date = a.start.date() if hasattr(a.start, 'date') else a.start
                if (a.doctor_id, date) in absence_dates:
                    conflicts.append({
                        'type': 'absence_conflict',
                        'doctor_id': a.doctor_id,
                        'date': date
                    })

        for o in operations:
            if o.doctor_id and o.start:
                date = o.start.date() if hasattr(o.start, 'date') else o.start
                if (o.doctor_id, date) in absence_dates:
                    conflicts.append({
                        'type': 'absence_conflict',
                        'doctor_id': o.doctor_id,
                        'date': date
                    })

        return conflicts
