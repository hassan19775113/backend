"""
Chart-Daten-Generatoren für das Ärzte-Dashboard.

Dieses Modul erzeugt Chart.js-kompatible Datenstrukturen für:
- Terminvolumen-Balkendiagramme
- Auslastungs-Trends (Line Charts)
- Peak-Times Heatmap
- Arzt-Vergleiche
- Satisfaction Scatter Plot
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

from praxi_backend.appointments.models import Appointment
from praxi_backend.core.models import User

from .doctor_kpis import (
    get_active_doctors,
    get_doctor_profile,
    calculate_doctor_utilization,
    calculate_appointment_volume,
    calculate_no_show_rate,
    calculate_treatment_duration,
    _generate_demo_satisfaction,
    _generate_demo_documentation,
    doctor_display_name,
)


# ============================================================================
# Terminvolumen pro Arzt (Bar Chart)
# ============================================================================

def get_appointment_volume_chart(days: int = 30) -> dict[str, Any]:
    """
    Generiert Balkendiagramm für Terminvolumen pro Arzt.
    """
    doctors = get_active_doctors()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz)
    
    labels = []
    completed_data = []
    scheduled_data = []
    cancelled_data = []
    colors = []
    
    for doctor in doctors:
        appointments = Appointment.objects.using('default').filter(
            doctor=doctor,
            start_time__gte=start_dt,
            start_time__lte=end_dt,
        )
        
        labels.append(doctor_display_name(doctor))
        colors.append(doctor.calendar_color or '#1E90FF')
        completed_data.append(appointments.filter(status='completed').count())
        scheduled_data.append(appointments.filter(status__in=['scheduled', 'confirmed']).count())
        cancelled_data.append(appointments.filter(status='cancelled').count())
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Abgeschlossen',
                'data': completed_data,
                'backgroundColor': '#28A745',
            },
            {
                'label': 'Geplant',
                'data': scheduled_data,
                'backgroundColor': '#007BFF',
            },
            {
                'label': 'Storniert',
                'data': cancelled_data,
                'backgroundColor': '#DC3545',
            },
        ],
        'doctor_colors': colors,
    }


# ============================================================================
# Auslastungs-Vergleich (Bar Chart)
# ============================================================================

def get_utilization_comparison_chart(days: int = 30) -> dict[str, Any]:
    """
    Generiert Balkendiagramm für Auslastungsvergleich.
    """
    doctors = get_active_doctors()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    labels = []
    utilization_data = []
    colors = []
    
    for doctor in doctors:
        util = calculate_doctor_utilization(doctor, start_date, end_date)
        labels.append(doctor_display_name(doctor))
        utilization_data.append(util['utilization'])
        colors.append(doctor.calendar_color or '#1E90FF')
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Auslastung (%)',
                'data': utilization_data,
                'backgroundColor': colors,
                'borderWidth': 0,
            },
        ],
    }


# ============================================================================
# Auslastungs-Trend (Line Chart)
# ============================================================================

def get_utilization_trend_chart(doctor_id: int | None = None, weeks: int = 12) -> dict[str, Any]:
    """
    Generiert Liniendiagramm für Auslastungstrend über Wochen.
    """
    if doctor_id:
        try:
            doctors = [User.objects.using('default').get(id=doctor_id)]
        except User.DoesNotExist:
            doctors = []
    else:
        doctors = get_active_doctors()[:5]  # Max 5 für Übersichtlichkeit
    
    end_date = date.today()
    
    labels = []
    for i in range(weeks, 0, -1):
        week_end = end_date - timedelta(days=(i - 1) * 7)
        labels.append(week_end.strftime('KW %W'))
    
    datasets = []
    
    for doctor in doctors:
        data = []
        for i in range(weeks, 0, -1):
            week_end = end_date - timedelta(days=(i - 1) * 7)
            week_start = week_end - timedelta(days=6)
            util = calculate_doctor_utilization(doctor, week_start, week_end)
            data.append(util['utilization'])
        
        datasets.append({
            'label': doctor_display_name(doctor),
            'data': data,
            'borderColor': doctor.calendar_color or '#1E90FF',
            'backgroundColor': 'transparent',
            'fill': False,
            'tension': 0.3,
        })
    
    return {
        'labels': labels,
        'datasets': datasets,
    }


# ============================================================================
# No-Show Rate Vergleich (Bar Chart)
# ============================================================================

def get_no_show_comparison_chart(days: int = 30) -> dict[str, Any]:
    """
    Generiert Balkendiagramm für No-Show-Raten-Vergleich.
    """
    doctors = get_active_doctors()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    labels = []
    no_show_data = []
    show_data = []
    
    for doctor in doctors:
        ns = calculate_no_show_rate(doctor, start_date, end_date)
        labels.append(doctor_display_name(doctor))
        no_show_data.append(ns['no_show_rate'])
        show_data.append(ns['show_rate'])
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Erschienen (%)',
                'data': show_data,
                'backgroundColor': '#28A745',
            },
            {
                'label': 'No-Show (%)',
                'data': no_show_data,
                'backgroundColor': '#DC3545',
            },
        ],
    }


# ============================================================================
# Wöchentliches Terminvolumen (Line Chart)
# ============================================================================

def get_weekly_volume_chart(doctor_id: int | None = None, weeks: int = 12) -> dict[str, Any]:
    """
    Generiert Liniendiagramm für wöchentliches Terminvolumen.
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=weeks * 7)
    
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz)
    
    base_query = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    )
    
    if doctor_id:
        base_query = base_query.filter(doctor_id=doctor_id)
    
    # Wöchentlich gruppieren
    weekly_data = (
        base_query
        .annotate(week=TruncWeek('start_time'))
        .values('week')
        .annotate(
            total=Count('id'),
            completed=Count('id', filter=Q(status='completed')),
        )
        .order_by('week')
    )
    
    # In Liste umwandeln
    labels = []
    total_data = []
    completed_data = []
    
    for w in weekly_data:
        labels.append(w['week'].strftime('KW %W'))
        total_data.append(w['total'])
        completed_data.append(w['completed'])
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Gesamt',
                'data': total_data,
                'borderColor': '#007BFF',
                'backgroundColor': 'rgba(0, 123, 255, 0.1)',
                'fill': True,
                'tension': 0.3,
            },
            {
                'label': 'Abgeschlossen',
                'data': completed_data,
                'borderColor': '#28A745',
                'backgroundColor': 'rgba(40, 167, 69, 0.1)',
                'fill': True,
                'tension': 0.3,
            },
        ],
    }


# ============================================================================
# Peak-Times Heatmap Daten
# ============================================================================

def get_peak_times_heatmap(doctor_id: int, days: int = 30) -> dict[str, Any]:
    """
    Generiert Heatmap-Daten für Peak-Times eines Arztes.
    """
    try:
        doctor = User.objects.using('default').get(id=doctor_id)
    except User.DoesNotExist:
        return {'heatmap': [], 'working_hours': [], 'max_value': 0}
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()), tz)
    
    appointments = Appointment.objects.using('default').filter(
        doctor=doctor,
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status__in=['completed', 'confirmed', 'scheduled'],
    )
    
    # Matrix: 7 Tage × 24 Stunden
    matrix = [[0 for _ in range(24)] for _ in range(7)]
    
    for appt in appointments:
        local_time = timezone.localtime(appt.start_time)
        weekday = local_time.weekday()
        hour = local_time.hour
        matrix[weekday][hour] += 1
    
    working_hours = list(range(8, 19))
    weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag']
    
    max_val = max(max(row[8:19]) for row in matrix[:5])
    
    heatmap_data = []
    for day_idx, day_name in enumerate(weekdays):
        for hour in working_hours:
            value = matrix[day_idx][hour]
            heatmap_data.append({
                'day': day_name,
                'day_idx': day_idx,
                'hour': hour,
                'value': value,
                'intensity': round(value / max(1, max_val) * 100),
            })
    
    return {
        'heatmap': heatmap_data,
        'working_hours': working_hours,
        'weekdays': weekdays,
        'max_value': max_val,
        'matrix': [row[8:19] for row in matrix[:5]],
    }


# ============================================================================
# Zufriedenheit vs. Behandlungsdauer (Scatter Plot)
# ============================================================================

def get_satisfaction_duration_scatter(days: int = 30) -> dict[str, Any]:
    """
    Generiert Scatter Plot Daten: Behandlungsdauer vs. Zufriedenheit.
    """
    doctors = get_active_doctors()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    data_points = []
    
    for doctor in doctors:
        duration = calculate_treatment_duration(doctor, start_date, end_date)
        satisfaction = _generate_demo_satisfaction(doctor.id)
        
        data_points.append({
            'x': duration['avg_actual'],
            'y': satisfaction['score'],
            'label': doctor_display_name(doctor),
            'color': doctor.calendar_color or '#1E90FF',
            'doctor_id': doctor.id,
        })
    
    return {
        'datasets': [
            {
                'label': 'Ärzte',
                'data': [{'x': p['x'], 'y': p['y']} for p in data_points],
                'backgroundColor': [p['color'] for p in data_points],
                'pointRadius': 10,
                'pointHoverRadius': 12,
            },
        ],
        'labels': [p['label'] for p in data_points],
        'data_points': data_points,
    }


# ============================================================================
# Dokumentations-Compliance Vergleich
# ============================================================================

def get_documentation_comparison_chart(days: int = 30) -> dict[str, Any]:
    """
    Generiert Balkendiagramm für Dokumentations-Compliance.
    """
    doctors = get_active_doctors()
    
    labels = []
    completed_data = []
    pending_data = []
    overdue_data = []
    
    for doctor in doctors:
        doc = _generate_demo_documentation(doctor.id)
        labels.append(doctor_display_name(doctor))
        completed_data.append(doc['completed'])
        pending_data.append(doc['pending'] - doc['overdue'])
        overdue_data.append(doc['overdue'])
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Abgeschlossen',
                'data': completed_data,
                'backgroundColor': '#28A745',
            },
            {
                'label': 'Offen',
                'data': pending_data,
                'backgroundColor': '#FFC107',
            },
            {
                'label': 'Überfällig',
                'data': overdue_data,
                'backgroundColor': '#DC3545',
            },
        ],
    }


# ============================================================================
# Neupatienten-Quote Vergleich
# ============================================================================

def get_new_patient_comparison_chart(days: int = 30) -> dict[str, Any]:
    """
    Generiert Tortendiagramm-Daten für Neupatienten vs. Bestandspatienten.
    """
    from .doctor_kpis import calculate_new_patient_rate
    
    doctors = get_active_doctors()
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    labels = []
    new_data = []
    returning_data = []
    
    for doctor in doctors:
        np = calculate_new_patient_rate(doctor, start_date, end_date)
        labels.append(doctor_display_name(doctor))
        new_data.append(np['new_patients'])
        returning_data.append(np['returning_patients'])
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Neupatienten',
                'data': new_data,
                'backgroundColor': '#17A2B8',
            },
            {
                'label': 'Bestandspatienten',
                'data': returning_data,
                'backgroundColor': '#6C757D',
            },
        ],
    }


# ============================================================================
# Leistungsübersicht Tabelle
# ============================================================================

def get_services_table_data(doctor_id: int) -> list[dict]:
    """
    Generiert Tabellendaten für Leistungsübersicht.
    """
    from .doctor_kpis import _generate_demo_services
    
    services = _generate_demo_services(doctor_id)
    
    total_count = sum(s['count'] for s in services)
    total_points = sum(s['total_points'] for s in services)
    
    for s in services:
        s['share'] = round(s['count'] / max(1, total_count) * 100, 1)
    
    return {
        'services': services,
        'total_count': total_count,
        'total_points': total_points,
    }


# ============================================================================
# Arzt-Ranking Tabelle
# ============================================================================

def get_doctor_ranking_table() -> list[dict]:
    """
    Generiert Ranking-Tabelle für alle Ärzte.
    """
    doctors = get_active_doctors()
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    rankings = []
    
    for doctor in doctors:
        util = calculate_doctor_utilization(doctor, start_date, end_date)
        volume = calculate_appointment_volume(doctor, start_date, end_date)
        no_show = calculate_no_show_rate(doctor, start_date, end_date)
        satisfaction = _generate_demo_satisfaction(doctor.id)
        documentation = _generate_demo_documentation(doctor.id)
        
        # Gesamt-Score berechnen (gewichteter Durchschnitt)
        score = (
            util['utilization'] * 0.25 +
            volume['completion_rate'] * 0.2 +
            (100 - no_show['no_show_rate']) * 0.15 +
            satisfaction['score'] * 20 * 0.25 +
            documentation['compliance_rate'] * 0.15
        )
        
        rankings.append({
            'rank': 0,
            'doctor_id': doctor.id,
            'name': doctor_display_name(doctor),
            'color': doctor.calendar_color or '#1E90FF',
            'utilization': util['utilization'],
            'appointments': volume['total'],
            'no_show_rate': no_show['no_show_rate'],
            'satisfaction': satisfaction['score'],
            'documentation': documentation['compliance_rate'],
            'score': round(score, 1),
        })
    
    # Nach Score sortieren
    rankings.sort(key=lambda x: x['score'], reverse=True)
    for i, r in enumerate(rankings):
        r['rank'] = i + 1
    
    return rankings


# ============================================================================
# Sammelfunktion
# ============================================================================

def get_all_doctor_charts(doctor_id: int | None = None, days: int = 30) -> dict[str, Any]:
    """
    Sammelt alle Chart-Daten für das Ärzte-Dashboard.
    """
    charts = {
        'appointment_volume': get_appointment_volume_chart(days),
        'utilization_comparison': get_utilization_comparison_chart(days),
        'utilization_trend': get_utilization_trend_chart(doctor_id, weeks=12),
        'no_show_comparison': get_no_show_comparison_chart(days),
        'weekly_volume': get_weekly_volume_chart(doctor_id, weeks=12),
        'documentation_comparison': get_documentation_comparison_chart(days),
        'new_patient_comparison': get_new_patient_comparison_chart(days),
        'satisfaction_scatter': get_satisfaction_duration_scatter(days),
        'ranking': get_doctor_ranking_table(),
    }
    
    if doctor_id:
        charts['peak_times'] = get_peak_times_heatmap(doctor_id, days)
        charts['services'] = get_services_table_data(doctor_id)
    
    return charts
