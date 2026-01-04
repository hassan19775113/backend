"""
Scheduling Charts - Visualisierungen für Scheduling KPIs
"""
from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Count
from django.db.models.functions import TruncDate, TruncWeek
from django.utils import timezone

from praxi_backend.appointments.models import Appointment
from .scheduling_kpis import (
    get_scheduling_date_ranges,
    calculate_slot_utilization,
    calculate_no_show_rate,
    calculate_cancellation_rate,
    calculate_doctor_capacity_utilization,
    calculate_room_capacity_utilization,
    get_scheduling_trends,
)


def get_utilization_trend_chart(days: int = 30) -> dict[str, Any]:
    """Line Chart: Auslastung pro Tag."""
    tz = timezone.get_current_timezone()
    now = timezone.now()
    start_date = (now - timedelta(days=days-1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    
    daily_counts = (
        Appointment.objects.using('default')
        .filter(
            start_time__gte=start_date,
            status__in=['scheduled', 'confirmed', 'completed']
        )
        .annotate(date=TruncDate('start_time'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    
    counts_dict = {d['date']: d['count'] for d in daily_counts}
    
    labels = []
    data = []
    current = start_date.date()
    end = now.date()
    
    while current <= end:
        labels.append(current.strftime('%d.%m'))
        data.append(counts_dict.get(current, 0))
        current += timedelta(days=1)
    
    return {
        'labels': labels,
        'datasets': [{
            'label': 'Gebuchte Termine',
            'data': data,
            'borderColor': '#1A73E8',
            'backgroundColor': 'rgba(26, 115, 232, 0.1)',
            'fill': True,
            'tension': 0.4,
        }]
    }


def get_completion_rate_trend() -> dict[str, Any]:
    """Line Chart: Completion Rate über Zeit (12 Wochen)."""
    trends = get_scheduling_trends()
    weeks = trends['weeks']
    
    labels = [w['week'] for w in weeks]
    completion_data = [w['completion_rate'] for w in weeks]
    no_show_data = [round((w['no_show'] / w['total']) * 100, 1) if w['total'] > 0 else 0 for w in weeks]
    cancellation_data = [round((w['cancelled'] / w['total']) * 100, 1) if w['total'] > 0 else 0 for w in weeks]
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Abschlussrate %',
                'data': completion_data,
                'borderColor': '#34A853',
                'backgroundColor': 'rgba(52, 168, 83, 0.1)',
                'fill': False,
                'tension': 0.4,
            },
            {
                'label': 'No-Show Rate %',
                'data': no_show_data,
                'borderColor': '#EA4335',
                'backgroundColor': 'rgba(234, 67, 53, 0.1)',
                'fill': False,
                'tension': 0.4,
            },
            {
                'label': 'Stornierungsrate %',
                'data': cancellation_data,
                'borderColor': '#FBBC05',
                'backgroundColor': 'rgba(251, 188, 5, 0.1)',
                'fill': False,
                'tension': 0.4,
            },
        ]
    }


def get_doctor_utilization_chart() -> dict[str, Any]:
    """Bar Chart: Arzt-Auslastung."""
    utilization = calculate_doctor_capacity_utilization()
    
    labels = [d['name'] for d in utilization]
    data = [d['utilization'] for d in utilization]
    colors = [d['color'] for d in utilization]
    
    return {
        'labels': labels,
        'datasets': [{
            'label': 'Auslastung %',
            'data': data,
            'backgroundColor': colors,
            'borderRadius': 8,
        }]
    }


def get_room_utilization_chart() -> dict[str, Any]:
    """Bar Chart: Raum-Auslastung."""
    utilization = calculate_room_capacity_utilization()
    
    labels = [r['name'] for r in utilization]
    data = [r['utilization'] for r in utilization]
    colors = [r['color'] for r in utilization]
    
    return {
        'labels': labels,
        'datasets': [{
            'label': 'Auslastung %',
            'data': data,
            'backgroundColor': colors,
            'borderRadius': 8,
        }]
    }


def get_status_funnel() -> dict[str, Any]:
    """Funnel: Termin-Status-Verteilung (Anfrage -> Bestätigt -> Abgeschlossen)."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges['last_30']
    
    appointments = Appointment.objects.using('default').filter(
        created_at__gte=last_30_start,
    )
    
    total = appointments.count()
    scheduled = appointments.filter(status='scheduled').count()
    confirmed = appointments.filter(status='confirmed').count()
    completed = appointments.filter(status='completed').count()
    cancelled = appointments.filter(status='cancelled').count()
    
    # Funnel-Daten
    funnel_data = [
        {'stage': 'Gebucht', 'count': total, 'color': '#1A73E8'},
        {'stage': 'Bestätigt', 'count': confirmed + completed, 'color': '#34A853'},
        {'stage': 'Abgeschlossen', 'count': completed, 'color': '#00BCD4'},
    ]
    
    # Conversion Rates
    if total > 0:
        confirmation_rate = round(((confirmed + completed) / total) * 100, 1)
        completion_rate = round((completed / total) * 100, 1)
    else:
        confirmation_rate = 0
        completion_rate = 0
    
    return {
        'funnel': funnel_data,
        'total': total,
        'confirmed': confirmed + completed,
        'completed': completed,
        'cancelled': cancelled,
        'confirmation_rate': confirmation_rate,
        'completion_rate': completion_rate,
    }


def get_lead_time_distribution() -> dict[str, Any]:
    """Bar Chart: Lead Time Verteilung."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges['last_30']
    
    appointments = Appointment.objects.using('default').filter(
        created_at__gte=last_30_start,
        status__in=['scheduled', 'confirmed', 'completed'],
    ).only('created_at', 'start_time')
    
    # Kategorien
    same_day = 0
    next_day = 0
    within_week = 0
    within_month = 0
    over_month = 0
    
    for appt in appointments:
        delta = appt.start_time - appt.created_at
        days = delta.days
        
        if days == 0:
            same_day += 1
        elif days == 1:
            next_day += 1
        elif days <= 7:
            within_week += 1
        elif days <= 30:
            within_month += 1
        else:
            over_month += 1
    
    return {
        'labels': ['Gleicher Tag', 'Nächster Tag', '2-7 Tage', '8-30 Tage', '> 30 Tage'],
        'datasets': [{
            'label': 'Anzahl Termine',
            'data': [same_day, next_day, within_week, within_month, over_month],
            'backgroundColor': ['#EA4335', '#FBBC05', '#34A853', '#1A73E8', '#9C27B0'],
            'borderRadius': 8,
        }]
    }


def get_hourly_load_chart() -> dict[str, Any]:
    """Bar Chart: Termine pro Stunde."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges['last_30']
    
    from django.db.models.functions import ExtractHour
    
    hourly = (
        Appointment.objects.using('default')
        .filter(start_time__gte=last_30_start, start_time__lte=last_30_end)
        .annotate(hour=ExtractHour('start_time'))
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('hour')
    )
    
    hourly_dict = {h['hour']: h['count'] for h in hourly}
    
    # Nur Geschäftszeiten (7-20 Uhr)
    labels = [f'{h:02d}:00' for h in range(7, 21)]
    data = [hourly_dict.get(h, 0) for h in range(7, 21)]
    
    # Farben basierend auf Auslastung
    max_count = max(data) if data else 1
    colors = []
    for count in data:
        intensity = count / max_count if max_count > 0 else 0
        if intensity > 0.8:
            colors.append('#EA4335')  # Rot - Überlastet
        elif intensity > 0.5:
            colors.append('#FBBC05')  # Gelb - Hoch
        elif intensity > 0.2:
            colors.append('#34A853')  # Grün - Normal
        else:
            colors.append('#9AA0A6')  # Grau - Niedrig
    
    return {
        'labels': labels,
        'datasets': [{
            'label': 'Termine',
            'data': data,
            'backgroundColor': colors,
            'borderRadius': 4,
        }]
    }


def get_weekday_load_chart() -> dict[str, Any]:
    """Bar Chart: Termine pro Wochentag."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges['last_30']
    
    from django.db.models.functions import ExtractWeekDay
    
    daily = (
        Appointment.objects.using('default')
        .filter(start_time__gte=last_30_start, start_time__lte=last_30_end)
        .annotate(weekday=ExtractWeekDay('start_time'))
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('weekday')
    )
    
    # Django: 1=Sonntag, 2=Montag, ..., 7=Samstag
    django_to_python = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
    day_names = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    
    data = [0] * 7
    for d in daily:
        py_day = django_to_python.get(d['weekday'], 0)
        data[py_day] = d['count']
    
    # Farben
    max_count = max(data) if data else 1
    colors = []
    for count in data:
        intensity = count / max_count if max_count > 0 else 0
        if intensity > 0.8:
            colors.append('#1A73E8')
        elif intensity > 0.5:
            colors.append('#34A853')
        elif intensity > 0.2:
            colors.append('#FBBC05')
        else:
            colors.append('#9AA0A6')
    
    return {
        'labels': day_names,
        'datasets': [{
            'label': 'Termine',
            'data': data,
            'backgroundColor': colors,
            'borderRadius': 8,
        }]
    }


def get_efficiency_gauge() -> dict[str, Any]:
    """Gauge-Daten für Effizienz-Score."""
    from .scheduling_kpis import calculate_scheduling_efficiency
    
    efficiency = calculate_scheduling_efficiency()
    
    return {
        'score': efficiency['efficiency_score'],
        'rating': efficiency['rating'],
        'rating_label': efficiency['rating_label'],
        'rating_color': efficiency['rating_color'],
        'components': efficiency['components'],
    }


def get_all_scheduling_charts() -> dict[str, Any]:
    """Sammelt alle Scheduling-Charts."""
    return {
        'utilization_trend': get_utilization_trend_chart(),
        'completion_rate_trend': get_completion_rate_trend(),
        'doctor_utilization': get_doctor_utilization_chart(),
        'room_utilization': get_room_utilization_chart(),
        'status_funnel': get_status_funnel(),
        'lead_time_distribution': get_lead_time_distribution(),
        'hourly_load': get_hourly_load_chart(),
        'weekday_load': get_weekday_load_chart(),
        'efficiency_gauge': get_efficiency_gauge(),
    }
