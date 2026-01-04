"""
Chart-Daten für das Admin-Dashboard
Generiert JSON-Daten für Chart.js
"""
from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from praxi_backend.core.models import User
from praxi_backend.appointments.models import (
    Appointment,
    AppointmentType,
    Operation,
    Resource,
)


def get_appointments_per_day(days: int = 30) -> dict[str, Any]:
    """Line Chart: Termine pro Tag (letzte X Tage)."""
    tz = timezone.get_current_timezone()
    now = timezone.now()
    start_date = (now - timedelta(days=days-1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    
    # Termine gruppiert nach Tag
    daily_counts = (
        Appointment.objects.using('default')
        .filter(start_time__gte=start_date)
        .annotate(date=TruncDate('start_time'))
        .values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )
    
    # Alle Tage befüllen (auch ohne Termine)
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
            'label': 'Termine',
            'data': data,
            'borderColor': '#1A73E8',
            'backgroundColor': 'rgba(26, 115, 232, 0.1)',
            'fill': True,
            'tension': 0.4,
        }]
    }


def get_operations_per_doctor() -> dict[str, Any]:
    """Bar Chart: Operationen pro Arzt (letzter Monat)."""
    tz = timezone.get_current_timezone()
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # OPs pro Chirurg
    ops_by_surgeon = (
        Operation.objects.using('default')
        .filter(start_time__gte=month_start)
        .values('primary_surgeon__id', 'primary_surgeon__first_name', 'primary_surgeon__last_name', 'primary_surgeon__calendar_color')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    labels = []
    data = []
    colors = []
    
    for op in ops_by_surgeon:
        name = f"{op['primary_surgeon__first_name'] or ''} {op['primary_surgeon__last_name'] or ''}".strip()
        if not name:
            name = f"Arzt #{op['primary_surgeon__id']}"
        labels.append(name)
        data.append(op['count'])
        colors.append(op['primary_surgeon__calendar_color'] or '#1A73E8')
    
    return {
        'labels': labels,
        'datasets': [{
            'label': 'Operationen',
            'data': data,
            'backgroundColor': colors,
            'borderRadius': 8,
        }]
    }


def get_appointment_types_distribution() -> dict[str, Any]:
    """Pie Chart: Verteilung der Terminarten (letzter Monat)."""
    tz = timezone.get_current_timezone()
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Termine nach Typ
    by_type = (
        Appointment.objects.using('default')
        .filter(start_time__gte=month_start, type__isnull=False)
        .values('type__id', 'type__name', 'type__color')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # Termine ohne Typ
    no_type_count = (
        Appointment.objects.using('default')
        .filter(start_time__gte=month_start, type__isnull=True)
        .count()
    )
    
    labels = []
    data = []
    colors = []
    
    for t in by_type:
        labels.append(t['type__name'])
        data.append(t['count'])
        colors.append(t['type__color'] or '#9AA0A6')
    
    if no_type_count > 0:
        labels.append('Ohne Typ')
        data.append(no_type_count)
        colors.append('#9AA0A6')
    
    return {
        'labels': labels,
        'datasets': [{
            'data': data,
            'backgroundColor': colors,
            'borderWidth': 2,
            'borderColor': '#ffffff',
        }]
    }


def get_room_utilization_chart() -> dict[str, Any]:
    """Bar Chart: Raum-Auslastung."""
    from .kpis import calculate_room_utilization
    
    utilization = calculate_room_utilization()
    
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


def get_hourly_heatmap() -> dict[str, Any]:
    """Heatmap: Termine nach Stunde (0-23) und Wochentag."""
    from django.db.models.functions import ExtractHour, ExtractWeekDay
    
    tz = timezone.get_current_timezone()
    now = timezone.now()
    start_date = now - timedelta(days=30)
    
    # Termine nach Stunde und Wochentag
    heatmap_data = (
        Appointment.objects.using('default')
        .filter(start_time__gte=start_date)
        .annotate(
            hour=ExtractHour('start_time'),
            weekday=ExtractWeekDay('start_time')
        )
        .values('hour', 'weekday')
        .annotate(count=Count('id'))
    )
    
    # Initialisiere 7x24 Matrix
    day_names = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    django_to_python = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
    
    matrix = [[0 for _ in range(24)] for _ in range(7)]
    
    for row in heatmap_data:
        py_day = django_to_python.get(row['weekday'], 0)
        hour = row['hour']
        matrix[py_day][hour] = row['count']
    
    # Für Chart.js Heatmap-Format
    datasets = []
    for day_idx, day_name in enumerate(day_names):
        for hour in range(24):
            count = matrix[day_idx][hour]
            if count > 0:
                datasets.append({
                    'x': hour,
                    'y': day_idx,
                    'v': count,
                })
    
    return {
        'labels': {
            'x': [f'{h:02d}:00' for h in range(24)],
            'y': day_names,
        },
        'data': datasets,
        'matrix': matrix,
    }


def get_status_distribution() -> dict[str, Any]:
    """Doughnut Chart: Status-Verteilung der Termine."""
    tz = timezone.get_current_timezone()
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    by_status = (
        Appointment.objects.using('default')
        .filter(start_time__gte=month_start)
        .values('status')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    status_config = {
        'scheduled': {'label': 'Geplant', 'color': '#FBBC05'},
        'confirmed': {'label': 'Bestätigt', 'color': '#1A73E8'},
        'completed': {'label': 'Abgeschlossen', 'color': '#34A853'},
        'cancelled': {'label': 'Storniert', 'color': '#EA4335'},
    }
    
    labels = []
    data = []
    colors = []
    
    for s in by_status:
        config = status_config.get(s['status'], {'label': s['status'], 'color': '#9AA0A6'})
        labels.append(config['label'])
        data.append(s['count'])
        colors.append(config['color'])
    
    return {
        'labels': labels,
        'datasets': [{
            'data': data,
            'backgroundColor': colors,
            'borderWidth': 0,
            'cutout': '60%',
        }]
    }


def get_all_charts() -> dict[str, Any]:
    """Sammelt alle Chart-Daten."""
    return {
        'appointments_per_day': get_appointments_per_day(),
        'operations_per_doctor': get_operations_per_doctor(),
        'appointment_types': get_appointment_types_distribution(),
        'room_utilization': get_room_utilization_chart(),
        'hourly_heatmap': get_hourly_heatmap(),
        'status_distribution': get_status_distribution(),
    }
