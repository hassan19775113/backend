"""
Chart-Daten-Generatoren für das Operations-Dashboard.

Dieses Modul erzeugt Chart.js-kompatible Datenstrukturen für:
- Patientenfluss-Visualisierung
- Ressourcen-Auslastungs-Heatmaps
- Stündliche Verteilung
- Engpass-Analysen
- Trend-Charts
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Count, Q
from django.db.models.functions import ExtractHour, ExtractWeekDay, TruncDate
from django.utils import timezone

from praxi_backend.appointments.models import (
    Appointment,
    Operation,
    PatientFlow,
    Resource,
)


# ============================================================================
# Farbpaletten
# ============================================================================

CHART_COLORS = [
    '#2E8B57',  # Grün
    '#1E90FF',  # Blau
    '#FF6347',  # Tomatenrot
    '#FFD700',  # Gold
    '#9370DB',  # Medium Purple
    '#20B2AA',  # Light Sea Green
    '#FF69B4',  # Hot Pink
    '#4682B4',  # Steel Blue
]

STATUS_COLORS = {
    'scheduled': '#6C757D',
    'confirmed': '#17A2B8',
    'cancelled': '#DC3545',
    'completed': '#28A745',
    'planned': '#6C757D',
    'running': '#FFC107',
    'done': '#28A745',
}

FLOW_STATUS_COLORS = {
    'registered': '#6C757D',
    'waiting': '#FFC107',
    'preparing': '#17A2B8',
    'in_treatment': '#28A745',
    'post_treatment': '#0D6EFD',
    'done': '#198754',
}


# ============================================================================
# Hilfsfunktionen
# ============================================================================

def get_date_range(days: int = 30) -> tuple[datetime, datetime]:
    """Berechnet Datumsbereiche für Abfragen."""
    from datetime import time
    today = timezone.localdate()
    start_date = today - timedelta(days=days)
    
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(today, time.max), tz)
    
    return start_dt, end_dt


# ============================================================================
# Chart-Generatoren
# ============================================================================

def get_utilization_gauge_chart(utilization: float) -> dict[str, Any]:
    """
    Erstellt Daten für ein Gauge-/Doughnut-Chart der Gesamtauslastung.
    """
    used = min(100, utilization)
    remaining = 100 - used
    
    # Farbe basierend auf Auslastung
    if used >= 90:
        color = '#DC3545'  # Rot - Überlastung
    elif used >= 75:
        color = '#FFC107'  # Gelb - Hoch
    elif used >= 50:
        color = '#28A745'  # Grün - Optimal
    else:
        color = '#17A2B8'  # Blau - Niedrig
    
    return {
        'labels': ['Ausgelastet', 'Verfügbar'],
        'datasets': [{
            'data': [used, remaining],
            'backgroundColor': [color, '#E9ECEF'],
            'borderWidth': 0,
        }],
        'centerText': f'{used}%',
    }


def get_patient_flow_funnel(flow_data: dict[str, Any]) -> dict[str, Any]:
    """
    Erstellt Daten für einen Patientenfluss-Funnel.
    """
    statuses = flow_data.get('statuses', [])
    
    labels = [s['label'] for s in statuses]
    data = [s['count'] for s in statuses]
    colors = [s['color'] for s in statuses]
    
    return {
        'labels': labels,
        'datasets': [{
            'label': 'Patienten',
            'data': data,
            'backgroundColor': colors,
            'borderWidth': 1,
            'borderColor': '#FFFFFF',
        }],
    }


def get_hourly_distribution_chart(days: int = 30) -> dict[str, Any]:
    """
    Erstellt ein Chart für die stündliche Verteilung.
    """
    start_dt, end_dt = get_date_range(days)
    
    # Termine nach Stunde
    appointments = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    ).annotate(
        hour=ExtractHour('start_time')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # OPs nach Stunde
    operations = Operation.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    ).annotate(
        hour=ExtractHour('start_time')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # Stunden 7-19
    hours = list(range(7, 20))
    appt_counts = {row['hour']: row['count'] for row in appointments}
    op_counts = {row['hour']: row['count'] for row in operations}
    
    labels = [f'{h}:00' for h in hours]
    appt_data = [appt_counts.get(h, 0) for h in hours]
    op_data = [op_counts.get(h, 0) for h in hours]
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Termine',
                'data': appt_data,
                'backgroundColor': '#2E8B57',
                'borderColor': '#2E8B57',
                'borderWidth': 2,
                'fill': True,
                'tension': 0.3,
            },
            {
                'label': 'OPs',
                'data': op_data,
                'backgroundColor': '#1E90FF',
                'borderColor': '#1E90FF',
                'borderWidth': 2,
                'fill': True,
                'tension': 0.3,
            },
        ],
    }


def get_resource_utilization_chart(days: int = 30) -> dict[str, Any]:
    """
    Erstellt ein horizontales Balkendiagramm für Ressourcenauslastung.
    """
    from .operations_kpis import calculate_resource_utilization, get_date_range as kpi_date_range
    
    _, _, start_dt, end_dt = kpi_date_range(days)
    resources = calculate_resource_utilization(start_dt, end_dt, days)
    
    all_resources = resources['resources'][:10]  # Top 10
    
    labels = [r['name'] for r in all_resources]
    data = [r['utilization'] for r in all_resources]
    colors = [r['color'] for r in all_resources]
    
    return {
        'labels': labels,
        'datasets': [{
            'label': 'Auslastung %',
            'data': data,
            'backgroundColor': colors,
            'borderWidth': 0,
            'borderRadius': 4,
        }],
    }


def get_room_heatmap_chart(days: int = 30) -> dict[str, Any]:
    """
    Erstellt Heatmap-Daten für Raumauslastung nach Wochentag und Stunde.
    """
    start_dt, end_dt = get_date_range(days)
    
    rooms = Resource.objects.using('default').filter(type='room', active=True)
    
    weekdays = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    hours = list(range(7, 20))
    
    heatmap_data = []
    
    for room in rooms[:5]:  # Top 5 Räume
        room_data = {
            'room_id': room.id,
            'room_name': room.name,
            'room_color': room.color,
            'data': [],
        }
        
        # Termine + OPs für diesen Raum
        appointments = Appointment.objects.using('default').filter(
            start_time__gte=start_dt,
            start_time__lte=end_dt,
            resources=room,
        ).annotate(
            weekday=ExtractWeekDay('start_time'),
            hour=ExtractHour('start_time'),
        ).values('weekday', 'hour').annotate(
            count=Count('id')
        )
        
        operations = Operation.objects.using('default').filter(
            start_time__gte=start_dt,
            start_time__lte=end_dt,
            op_room=room,
        ).annotate(
            weekday=ExtractWeekDay('start_time'),
            hour=ExtractHour('start_time'),
        ).values('weekday', 'hour').annotate(
            count=Count('id')
        )
        
        # Kombinieren
        counts = {}
        for row in appointments:
            # Django: 1=Sunday, 2=Monday, ..., 7=Saturday
            wd = (row['weekday'] - 2) % 7  # Convert to 0=Monday
            key = (wd, row['hour'])
            counts[key] = counts.get(key, 0) + row['count']
        
        for row in operations:
            wd = (row['weekday'] - 2) % 7
            key = (wd, row['hour'])
            counts[key] = counts.get(key, 0) + row['count']
        
        max_count = max(counts.values()) if counts else 1
        
        for wd_idx, wd_name in enumerate(weekdays):
            row_data = {
                'day': wd_name,
                'hours': [],
            }
            for h in hours:
                count = counts.get((wd_idx, h), 0)
                intensity = round((count / max_count) * 100, 1) if max_count > 0 else 0
                row_data['hours'].append({
                    'hour': h,
                    'count': count,
                    'intensity': intensity,
                })
            room_data['data'].append(row_data)
        
        heatmap_data.append(room_data)
    
    return {
        'rooms': heatmap_data,
        'hours': hours,
        'weekdays': weekdays,
    }


def get_status_distribution_chart(days: int = 30) -> dict[str, Any]:
    """
    Erstellt ein Doughnut-Chart für Statusverteilung.
    """
    start_dt, end_dt = get_date_range(days)
    
    # Termine
    appt_status = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    ).values('status').annotate(
        count=Count('id')
    )
    
    status_map = {
        'scheduled': 'Geplant',
        'confirmed': 'Bestätigt',
        'cancelled': 'Storniert',
        'completed': 'Abgeschlossen',
    }
    
    labels = []
    data = []
    colors = []
    
    for row in appt_status:
        status = row['status']
        labels.append(status_map.get(status, status))
        data.append(row['count'])
        colors.append(STATUS_COLORS.get(status, '#6C757D'))
    
    return {
        'labels': labels,
        'datasets': [{
            'data': data,
            'backgroundColor': colors,
            'borderWidth': 2,
            'borderColor': '#FFFFFF',
        }],
    }


def get_daily_trend_chart(days: int = 30) -> dict[str, Any]:
    """
    Erstellt ein Liniendiagramm für den täglichen Trend.
    """
    start_dt, end_dt = get_date_range(days)
    
    # Termine pro Tag
    appointments = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    ).annotate(
        day=TruncDate('start_time')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    # OPs pro Tag
    operations = Operation.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    ).annotate(
        day=TruncDate('start_time')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    appt_by_day = {row['day']: row['count'] for row in appointments}
    op_by_day = {row['day']: row['count'] for row in operations}
    
    # Alle Tage im Bereich
    current = start_dt.date()
    end = end_dt.date()
    
    labels = []
    appt_data = []
    op_data = []
    
    while current <= end:
        labels.append(current.strftime('%d.%m'))
        appt_data.append(appt_by_day.get(current, 0))
        op_data.append(op_by_day.get(current, 0))
        current += timedelta(days=1)
    
    return {
        'labels': labels,
        'datasets': [
            {
                'label': 'Termine',
                'data': appt_data,
                'borderColor': '#2E8B57',
                'backgroundColor': 'rgba(46, 139, 87, 0.1)',
                'borderWidth': 2,
                'fill': True,
                'tension': 0.3,
            },
            {
                'label': 'OPs',
                'data': op_data,
                'borderColor': '#1E90FF',
                'backgroundColor': 'rgba(30, 144, 255, 0.1)',
                'borderWidth': 2,
                'fill': True,
                'tension': 0.3,
            },
        ],
    }


def get_bottleneck_chart(bottleneck_data: dict[str, Any]) -> dict[str, Any]:
    """
    Erstellt ein Chart für Engpass-Faktoren.
    """
    factors = bottleneck_data.get('contributing_factors', [])
    
    labels = [f['name'] for f in factors]
    data = [f['score'] for f in factors]
    
    return {
        'labels': labels,
        'datasets': [{
            'label': 'Score',
            'data': data,
            'backgroundColor': ['#FF6384', '#36A2EB', '#FFCE56'],
            'borderWidth': 0,
        }],
    }


def get_punctuality_chart(punctuality_data: dict[str, Any]) -> dict[str, Any]:
    """
    Erstellt ein Doughnut-Chart für Pünktlichkeit.
    """
    return {
        'labels': ['Pünktlich', 'Leichte Verzögerung', 'Starke Verzögerung'],
        'datasets': [{
            'data': [
                punctuality_data.get('on_time_rate', 0),
                punctuality_data.get('slight_delay_rate', 0),
                punctuality_data.get('significant_delay_rate', 0),
            ],
            'backgroundColor': ['#28A745', '#FFC107', '#DC3545'],
            'borderWidth': 2,
            'borderColor': '#FFFFFF',
        }],
    }


def get_documentation_chart(documentation_data: dict[str, Any]) -> dict[str, Any]:
    """
    Erstellt ein Chart für Dokumentationsstatus.
    """
    return {
        'labels': ['Abgeschlossen', 'Ausstehend', 'Überfällig'],
        'datasets': [{
            'data': [
                documentation_data.get('completed', 0),
                documentation_data.get('pending', 0),
                documentation_data.get('overdue', 0),
            ],
            'backgroundColor': ['#28A745', '#FFC107', '#DC3545'],
            'borderWidth': 2,
            'borderColor': '#FFFFFF',
        }],
    }


def get_services_table(services_data: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Erstellt Tabellendaten für Leistungsübersicht.
    """
    return {
        'columns': ['Ziffer', 'Leistung', 'Anzahl', 'Punkte', 'Gesamt'],
        'rows': services_data[:15],
        'total_count': sum(s['count'] for s in services_data),
        'total_points': sum(s['total_points'] for s in services_data),
    }


def get_flow_times_chart(flow_times: dict[str, Any]) -> dict[str, Any]:
    """
    Erstellt ein Chart für Durchlaufzeiten.
    """
    return {
        'labels': ['Wartezeit', 'Vorbereitung', 'Behandlung', 'Nachbereitung'],
        'datasets': [{
            'label': 'Minuten',
            'data': [
                flow_times.get('avg_wait_time', 0),
                flow_times.get('avg_prep_time', 0),
                flow_times.get('avg_treatment_time', 0),
                flow_times.get('avg_post_time', 0),
            ],
            'backgroundColor': ['#FFC107', '#17A2B8', '#28A745', '#0D6EFD'],
            'borderWidth': 0,
            'borderRadius': 4,
        }],
    }


# ============================================================================
# Aggregierter Chart-Sammler
# ============================================================================

def get_all_operations_charts(days: int = 30, kpis: dict[str, Any] = None) -> dict[str, Any]:
    """
    Sammelt alle Chart-Daten für das Operations-Dashboard.
    """
    charts = {
        'hourly_distribution': get_hourly_distribution_chart(days),
        'resource_utilization': get_resource_utilization_chart(days),
        'room_heatmap': get_room_heatmap_chart(days),
        'status_distribution': get_status_distribution_chart(days),
        'daily_trend': get_daily_trend_chart(days),
    }
    
    # Wenn KPIs übergeben wurden, zusätzliche Charts erstellen
    if kpis:
        if 'utilization' in kpis:
            charts['utilization_gauge'] = get_utilization_gauge_chart(
                kpis['utilization'].get('utilization', 0)
            )
        
        if 'patient_flow' in kpis:
            charts['patient_flow'] = get_patient_flow_funnel(kpis['patient_flow'])
        
        if 'bottleneck' in kpis:
            charts['bottleneck'] = get_bottleneck_chart(kpis['bottleneck'])
        
        if 'punctuality' in kpis:
            charts['punctuality'] = get_punctuality_chart(kpis['punctuality'])
        
        if 'documentation' in kpis:
            charts['documentation'] = get_documentation_chart(kpis['documentation'])
        
        if 'services' in kpis:
            charts['services_table'] = get_services_table(kpis['services'])
        
        if 'flow_times' in kpis:
            charts['flow_times'] = get_flow_times_chart(kpis['flow_times'])
    
    return charts
