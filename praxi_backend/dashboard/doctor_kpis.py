"""
KPI-Berechnungen für das Ärzte-Dashboard.

Dieses Modul enthält alle Berechnungen für:
- Auslastungsquote pro Arzt
- Terminanzahl und Trends
- No-Show-Rate und Stornoquote
- Behandlungsdauer (geplant vs. tatsächlich)
- Patientenzufriedenheit
- Dokumentations-Compliance
- Neupatienten-Quote
- Leistungsvolumen
- Wartezeiten
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import ExtractHour, ExtractWeekDay, TruncDate, TruncWeek
from django.utils import timezone

from praxi_backend.appointments.models import (
    Appointment,
    DoctorHours,
    DoctorAbsence,
    PracticeHours,
    Resource,
)
from praxi_backend.core.models import User


# ============================================================================
# Hilfsfunktionen
# ============================================================================

def get_date_ranges() -> dict[str, tuple[datetime, datetime]]:
    """Berechnet Datumsbereiche für KPIs."""
    tz = timezone.get_current_timezone()
    now = timezone.now()
    today_start = timezone.make_aware(
        datetime.combine(now.date(), datetime.min.time()), tz
    )
    today_end = timezone.make_aware(
        datetime.combine(now.date(), datetime.max.time()), tz
    )
    
    # Diese Woche (Montag bis Sonntag)
    week_start = today_start - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    # Dieser Monat
    month_start = today_start.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_month - timedelta(seconds=1)
    
    # Letzte 30 Tage
    last_30_start = today_start - timedelta(days=29)
    
    # Letztes Quartal
    quarter_start = today_start - timedelta(days=90)
    
    return {
        'today': (today_start, today_end),
        'week': (week_start, week_end),
        'month': (month_start, month_end),
        'last_30': (last_30_start, today_end),
        'quarter': (quarter_start, today_end),
    }


def get_active_doctors() -> list[User]:
    """Holt alle aktiven Ärzte."""
    return list(
        User.objects.using('default')
        .filter(is_active=True, role__name='doctor')
        .order_by('last_name', 'first_name', 'id')
    )


def doctor_display_name(doctor: User) -> str:
    """Formatiert Arzt-Anzeigename."""
    full_name = doctor.get_full_name()
    if full_name:
        return f"Dr. {full_name}"
    return doctor.username


# ============================================================================
# Demo-Daten Generatoren
# ============================================================================

def _generate_demo_satisfaction(doctor_id: int) -> dict[str, Any]:
    """Generiert Demo-Patientenzufriedenheitsdaten."""
    random.seed(doctor_id + 7000)
    
    score = round(random.uniform(3.5, 5.0), 1)
    reviews_count = random.randint(15, 80)
    
    distribution = {
        5: random.randint(40, 70),
        4: random.randint(15, 35),
        3: random.randint(5, 15),
        2: random.randint(0, 5),
        1: random.randint(0, 3),
    }
    
    # Normalisieren
    total = sum(distribution.values())
    distribution = {k: round(v / total * 100, 1) for k, v in distribution.items()}
    
    recent_feedback = [
        "Sehr freundlich und kompetent!",
        "Nimmt sich Zeit für Erklärungen.",
        "Kurze Wartezeit, gute Behandlung.",
        "Etwas lange gewartet, aber sonst top.",
        "Kann ich nur empfehlen!",
    ]
    
    return {
        'score': score,
        'max_score': 5.0,
        'reviews_count': reviews_count,
        'distribution': distribution,
        'trend': round(random.uniform(-0.3, 0.5), 2),
        'recent_feedback': random.sample(recent_feedback, min(3, len(recent_feedback))),
    }


def _generate_demo_documentation(doctor_id: int) -> dict[str, Any]:
    """Generiert Demo-Dokumentationsstatus."""
    random.seed(doctor_id + 8000)
    
    total_docs = random.randint(80, 200)
    completed = random.randint(int(total_docs * 0.7), total_docs)
    pending = total_docs - completed
    overdue = random.randint(0, min(10, pending))
    
    compliance_rate = round(completed / total_docs * 100, 1) if total_docs > 0 else 0
    
    return {
        'total': total_docs,
        'completed': completed,
        'pending': pending,
        'overdue': overdue,
        'compliance_rate': compliance_rate,
        'avg_completion_time': round(random.uniform(0.5, 4.0), 1),  # Stunden
    }


def _generate_demo_services(doctor_id: int) -> list[dict]:
    """Generiert Demo-Leistungsdaten."""
    random.seed(doctor_id + 9000)
    
    services = [
        {'code': 'GOP 1', 'name': 'Beratung', 'points': 160, 'count': random.randint(50, 150)},
        {'code': 'GOP 3', 'name': 'Eingehende Beratung', 'points': 230, 'count': random.randint(20, 80)},
        {'code': 'GOP 5', 'name': 'Symptombezogene Untersuchung', 'points': 90, 'count': random.randint(100, 250)},
        {'code': 'GOP 7', 'name': 'Vollständige Untersuchung', 'points': 260, 'count': random.randint(30, 100)},
        {'code': 'GOP 8', 'name': 'Untersuchung eines Organsystems', 'points': 160, 'count': random.randint(40, 120)},
        {'code': 'EKG', 'name': 'Elektrokardiogramm', 'points': 250, 'count': random.randint(10, 50)},
        {'code': 'SONO', 'name': 'Sonographie', 'points': 350, 'count': random.randint(15, 60)},
    ]
    
    for s in services:
        s['total_points'] = s['points'] * s['count']
    
    return sorted(services, key=lambda x: x['count'], reverse=True)


def _generate_demo_waiting_times(doctor_id: int) -> dict[str, Any]:
    """Generiert Demo-Wartezeiten."""
    random.seed(doctor_id + 10000)
    
    return {
        'booking_lead_time': random.randint(3, 21),  # Tage bis Termin
        'waiting_room': round(random.uniform(5, 35), 1),  # Minuten im Wartezimmer
        'booking_lead_time_trend': round(random.uniform(-2, 3), 1),
        'waiting_room_trend': round(random.uniform(-5, 8), 1),
    }


# ============================================================================
# Auslastungsquote
# ============================================================================

def calculate_doctor_utilization(
    doctor: User,
    start_date: date,
    end_date: date
) -> dict[str, Any]:
    """
    Berechnet die Auslastungsquote eines Arztes.
    
    Formel: (Gebuchte Slots / Verfügbare Slots) × 100
    """
    tz = timezone.get_current_timezone()
    
    # Verfügbare Slots berechnen (basierend auf DoctorHours)
    total_available_minutes = 0
    current_date = start_date
    
    while current_date <= end_date:
        weekday = current_date.weekday()
        
        # Prüfen ob Abwesenheit
        is_absent = DoctorAbsence.objects.using('default').filter(
            doctor=doctor,
            active=True,
            start_date__lte=current_date,
            end_date__gte=current_date,
        ).exists()
        
        if not is_absent:
            # Arbeitszeiten des Arztes an diesem Wochentag
            hours = DoctorHours.objects.using('default').filter(
                doctor=doctor,
                weekday=weekday,
                active=True,
            )
            
            for h in hours:
                start_dt = datetime.combine(current_date, h.start_time)
                end_dt = datetime.combine(current_date, h.end_time)
                minutes = (end_dt - start_dt).seconds // 60
                total_available_minutes += minutes
        
        current_date += timedelta(days=1)
    
    # Gebuchte Slots
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz)
    
    appointments = Appointment.objects.using('default').filter(
        doctor=doctor,
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status__in=['scheduled', 'confirmed', 'completed'],
    )
    
    total_booked_minutes = 0
    for appt in appointments:
        duration = (appt.end_time - appt.start_time).seconds // 60
        total_booked_minutes += duration
    
    # Auslastungsquote berechnen
    if total_available_minutes > 0:
        utilization = round(total_booked_minutes / total_available_minutes * 100, 1)
    else:
        utilization = 0
    
    return {
        'utilization': min(100, utilization),
        'available_minutes': total_available_minutes,
        'booked_minutes': total_booked_minutes,
        'available_hours': round(total_available_minutes / 60, 1),
        'booked_hours': round(total_booked_minutes / 60, 1),
        'appointment_count': appointments.count(),
    }


# ============================================================================
# Terminanzahl und Trends
# ============================================================================

def calculate_appointment_volume(
    doctor: User,
    start_date: date,
    end_date: date
) -> dict[str, Any]:
    """
    Berechnet Terminvolumen und Durchschnitte.
    """
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz)
    
    appointments = Appointment.objects.using('default').filter(
        doctor=doctor,
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    )
    
    total = appointments.count()
    completed = appointments.filter(status='completed').count()
    scheduled = appointments.filter(status__in=['scheduled', 'confirmed']).count()
    cancelled = appointments.filter(status='cancelled').count()
    
    # Tage berechnen
    days = (end_date - start_date).days + 1
    weeks = max(1, days / 7)
    
    # Termine pro Tag (nach Datum gruppiert)
    daily_counts = (
        appointments
        .filter(status__in=['completed', 'confirmed', 'scheduled'])
        .annotate(day=TruncDate('start_time'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )
    
    daily_list = [d['count'] for d in daily_counts]
    avg_per_day = round(sum(daily_list) / max(1, len(daily_list)), 1) if daily_list else 0
    
    return {
        'total': total,
        'completed': completed,
        'scheduled': scheduled,
        'cancelled': cancelled,
        'avg_per_day': avg_per_day,
        'avg_per_week': round(total / weeks, 1),
        'daily_counts': list(daily_counts),
        'completion_rate': round(completed / max(1, total) * 100, 1),
    }


# ============================================================================
# No-Show-Rate
# ============================================================================

def calculate_no_show_rate(
    doctor: User,
    start_date: date,
    end_date: date
) -> dict[str, Any]:
    """
    Berechnet die No-Show-Rate eines Arztes.
    
    No-Show: Termin in der Vergangenheit mit Status 'scheduled' (nicht bestätigt/completed)
    """
    tz = timezone.get_current_timezone()
    now = timezone.now()
    
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt = min(
        timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz),
        now
    )
    
    # Nur vergangene Termine
    past_appointments = Appointment.objects.using('default').filter(
        doctor=doctor,
        start_time__gte=start_dt,
        start_time__lt=now,
    )
    
    total_past = past_appointments.count()
    no_shows = past_appointments.filter(status='scheduled').count()
    completed = past_appointments.filter(status='completed').count()
    
    no_show_rate = round(no_shows / max(1, total_past) * 100, 1)
    
    return {
        'no_show_rate': no_show_rate,
        'no_show_count': no_shows,
        'total_past': total_past,
        'completed': completed,
        'show_rate': round(100 - no_show_rate, 1),
    }


# ============================================================================
# Stornoquote
# ============================================================================

def calculate_cancellation_rate(
    doctor: User,
    start_date: date,
    end_date: date
) -> dict[str, Any]:
    """
    Berechnet die Stornoquote eines Arztes.
    """
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz)
    
    appointments = Appointment.objects.using('default').filter(
        doctor=doctor,
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    )
    
    total = appointments.count()
    cancelled = appointments.filter(status='cancelled').count()
    
    cancellation_rate = round(cancelled / max(1, total) * 100, 1)
    
    return {
        'cancellation_rate': cancellation_rate,
        'cancelled_count': cancelled,
        'total': total,
    }


# ============================================================================
# Durchschnittliche Behandlungsdauer
# ============================================================================

def calculate_treatment_duration(
    doctor: User,
    start_date: date,
    end_date: date
) -> dict[str, Any]:
    """
    Berechnet durchschnittliche Behandlungsdauer.
    
    Vergleicht geplante vs. tatsächliche Dauer (Demo: +/- 10-20%)
    """
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz)
    
    completed = Appointment.objects.using('default').filter(
        doctor=doctor,
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status='completed',
    )
    
    durations = []
    for appt in completed:
        planned = (appt.end_time - appt.start_time).seconds // 60
        durations.append(planned)
    
    if not durations:
        return {
            'avg_planned': 0,
            'avg_actual': 0,
            'efficiency': 100,
            'count': 0,
        }
    
    avg_planned = sum(durations) / len(durations)
    
    # Simulierte tatsächliche Dauer (leichte Variation)
    random.seed(doctor.id + 6000)
    variation = random.uniform(-0.1, 0.2)  # -10% bis +20%
    avg_actual = avg_planned * (1 + variation)
    
    efficiency = round(avg_planned / max(1, avg_actual) * 100, 1)
    
    return {
        'avg_planned': round(avg_planned, 1),
        'avg_actual': round(avg_actual, 1),
        'efficiency': min(120, efficiency),
        'count': len(durations),
        'total_hours': round(sum(durations) / 60, 1),
    }


# ============================================================================
# Neupatienten-Quote
# ============================================================================

def calculate_new_patient_rate(
    doctor: User,
    start_date: date,
    end_date: date
) -> dict[str, Any]:
    """
    Berechnet den Anteil neuer Patienten.
    
    Neu: Patient hat keinen früheren Termin bei diesem Arzt.
    """
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz)
    
    # Termine im Zeitraum
    appointments = Appointment.objects.using('default').filter(
        doctor=doctor,
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status__in=['completed', 'confirmed', 'scheduled'],
    )
    
    patient_ids = set(appointments.values_list('patient_id', flat=True))
    total_patients = len(patient_ids)
    
    if total_patients == 0:
        return {
            'new_patient_rate': 0,
            'new_patients': 0,
            'returning_patients': 0,
            'total_patients': 0,
        }
    
    # Prüfen welche Patienten vorher schon Termine hatten
    new_patients = 0
    for patient_id in patient_ids:
        had_previous = Appointment.objects.using('default').filter(
            doctor=doctor,
            patient_id=patient_id,
            start_time__lt=start_dt,
        ).exists()
        
        if not had_previous:
            new_patients += 1
    
    returning_patients = total_patients - new_patients
    new_patient_rate = round(new_patients / total_patients * 100, 1)
    
    return {
        'new_patient_rate': new_patient_rate,
        'new_patients': new_patients,
        'returning_patients': returning_patients,
        'total_patients': total_patients,
    }


# ============================================================================
# Peak-Times Heatmap
# ============================================================================

def calculate_peak_times(
    doctor: User,
    start_date: date,
    end_date: date
) -> dict[str, Any]:
    """
    Berechnet Peak-Times als Heatmap (Wochentag × Stunde).
    """
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz)
    
    appointments = Appointment.objects.using('default').filter(
        doctor=doctor,
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status__in=['completed', 'confirmed', 'scheduled'],
    )
    
    # Matrix: 7 Tage × 24 Stunden (aber nur 8-18 Uhr relevant)
    matrix = [[0 for _ in range(24)] for _ in range(7)]
    
    for appt in appointments:
        local_time = timezone.localtime(appt.start_time)
        weekday = local_time.weekday()
        hour = local_time.hour
        matrix[weekday][hour] += 1
    
    # Nur relevante Stunden (8-18)
    working_hours = list(range(8, 19))
    weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    
    # Maximum für Normalisierung
    max_val = max(max(row[8:19]) for row in matrix)
    
    heatmap_data = []
    for day_idx, day_name in enumerate(weekdays[:5]):  # Nur Mo-Fr
        row_data = []
        for hour in working_hours:
            value = matrix[day_idx][hour]
            intensity = round(value / max(1, max_val) * 100, 1)
            row_data.append({
                'hour': hour,
                'count': value,
                'intensity': intensity,
            })
        heatmap_data.append({
            'day': day_name,
            'hours': row_data,
        })
    
    return {
        'matrix': matrix,
        'heatmap': heatmap_data,
        'working_hours': working_hours,
        'max_value': max_val,
        'busiest_hour': max(range(8, 19), key=lambda h: sum(matrix[d][h] for d in range(5))),
        'busiest_day': weekdays[max(range(5), key=lambda d: sum(matrix[d][8:19]))],
    }


# ============================================================================
# Arzt-Übersicht
# ============================================================================

def get_doctor_profile(doctor: User) -> dict[str, Any]:
    """
    Holt Arzt-Profildaten.
    """
    # Arbeitszeiten
    hours = DoctorHours.objects.using('default').filter(
        doctor=doctor,
        active=True,
    ).order_by('weekday', 'start_time')
    
    weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    working_days = set()
    total_weekly_hours = 0
    
    for h in hours:
        working_days.add(weekdays[h.weekday])
        start_dt = datetime.combine(date.today(), h.start_time)
        end_dt = datetime.combine(date.today(), h.end_time)
        total_weekly_hours += (end_dt - start_dt).seconds / 3600
    
    return {
        'id': doctor.id,
        'username': doctor.username,
        'name': doctor_display_name(doctor),
        'first_name': doctor.first_name,
        'last_name': doctor.last_name,
        'email': doctor.email,
        'calendar_color': doctor.calendar_color or '#1E90FF',
        'working_days': sorted(working_days, key=lambda d: weekdays.index(d)),
        'weekly_hours': round(total_weekly_hours, 1),
        'is_active': doctor.is_active,
    }


# ============================================================================
# Gesamtauswertung für einen Arzt
# ============================================================================

def get_all_doctor_kpis(doctor_id: int, days: int = 30) -> dict[str, Any]:
    """
    Sammelt alle KPIs für einen einzelnen Arzt.
    """
    try:
        doctor = User.objects.using('default').get(id=doctor_id, role__name='doctor')
    except User.DoesNotExist:
        return {'error': 'Arzt nicht gefunden', 'doctor_id': doctor_id}
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    profile = get_doctor_profile(doctor)
    utilization = calculate_doctor_utilization(doctor, start_date, end_date)
    volume = calculate_appointment_volume(doctor, start_date, end_date)
    no_show = calculate_no_show_rate(doctor, start_date, end_date)
    cancellation = calculate_cancellation_rate(doctor, start_date, end_date)
    duration = calculate_treatment_duration(doctor, start_date, end_date)
    new_patients = calculate_new_patient_rate(doctor, start_date, end_date)
    peak_times = calculate_peak_times(doctor, start_date, end_date)
    
    # Demo-Daten
    satisfaction = _generate_demo_satisfaction(doctor_id)
    documentation = _generate_demo_documentation(doctor_id)
    services = _generate_demo_services(doctor_id)
    waiting_times = _generate_demo_waiting_times(doctor_id)
    
    return {
        'profile': profile,
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days,
        },
        'utilization': utilization,
        'volume': volume,
        'no_show': no_show,
        'cancellation': cancellation,
        'duration': duration,
        'new_patients': new_patients,
        'peak_times': peak_times,
        'satisfaction': satisfaction,
        'documentation': documentation,
        'services': services,
        'waiting_times': waiting_times,
    }


# ============================================================================
# Vergleichsdaten für alle Ärzte
# ============================================================================

def get_doctor_comparison_data(days: int = 30) -> dict[str, Any]:
    """
    Sammelt Vergleichsdaten für alle Ärzte.
    """
    doctors = get_active_doctors()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    comparison = []
    
    for doctor in doctors:
        profile = get_doctor_profile(doctor)
        utilization = calculate_doctor_utilization(doctor, start_date, end_date)
        volume = calculate_appointment_volume(doctor, start_date, end_date)
        no_show = calculate_no_show_rate(doctor, start_date, end_date)
        cancellation = calculate_cancellation_rate(doctor, start_date, end_date)
        new_patients = calculate_new_patient_rate(doctor, start_date, end_date)
        satisfaction = _generate_demo_satisfaction(doctor.id)
        documentation = _generate_demo_documentation(doctor.id)
        
        comparison.append({
            'doctor_id': doctor.id,
            'name': profile['name'],
            'color': profile['calendar_color'],
            'utilization': utilization['utilization'],
            'appointments': volume['total'],
            'completed': volume['completed'],
            'avg_per_day': volume['avg_per_day'],
            'no_show_rate': no_show['no_show_rate'],
            'cancellation_rate': cancellation['cancellation_rate'],
            'new_patient_rate': new_patients['new_patient_rate'],
            'satisfaction_score': satisfaction['score'],
            'documentation_compliance': documentation['compliance_rate'],
        })
    
    # Aggregierte Werte
    if comparison:
        avg_utilization = sum(d['utilization'] for d in comparison) / len(comparison)
        avg_no_show = sum(d['no_show_rate'] for d in comparison) / len(comparison)
        avg_satisfaction = sum(d['satisfaction_score'] for d in comparison) / len(comparison)
        total_appointments = sum(d['appointments'] for d in comparison)
    else:
        avg_utilization = avg_no_show = avg_satisfaction = total_appointments = 0
    
    return {
        'doctors': comparison,
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days,
        },
        'aggregates': {
            'doctor_count': len(doctors),
            'avg_utilization': round(avg_utilization, 1),
            'avg_no_show_rate': round(avg_no_show, 1),
            'avg_satisfaction': round(avg_satisfaction, 1),
            'total_appointments': total_appointments,
        },
    }
