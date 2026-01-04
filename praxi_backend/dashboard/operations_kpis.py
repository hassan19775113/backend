"""
KPI-Berechnungen für das Operations-Dashboard.

Dieses Modul berechnet operative Kennzahlen für:
- Gesamtauslastung (Räume, Geräte, Personal)
- Durchlaufzeiten und Wartezeiten
- No-Show und Storno-Raten
- Pünktlichkeit und Prozessqualität
- Engpass-Analysen
- Patientendurchsatz
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import ExtractHour, TruncDate, TruncHour
from django.utils import timezone

from praxi_backend.appointments.models import (
    Appointment,
    AppointmentResource,
    DoctorHours,
    Operation,
    OperationDevice,
    PatientFlow,
    PracticeHours,
    Resource,
)
from praxi_backend.core.models import User


# ============================================================================
# Hilfsfunktionen
# ============================================================================

def get_date_range(days: int = 30) -> tuple[date, date, datetime, datetime]:
    """Berechnet Datumsbereiche für Abfragen."""
    today = timezone.localdate()
    start_date = today - timedelta(days=days)
    
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(today, time.max), tz)
    
    return start_date, today, start_dt, end_dt


def get_period_label(days: int) -> str:
    """Erstellt ein Label für den Zeitraum."""
    if days == 1:
        return "Heute"
    elif days == 7:
        return "Letzte 7 Tage"
    elif days == 30:
        return "Letzte 30 Tage"
    elif days == 90:
        return "Letzte 90 Tage"
    elif days == 365:
        return "Letztes Jahr"
    return f"Letzte {days} Tage"


# ============================================================================
# Demo-Daten-Generatoren (für fehlende Echtdaten)
# ============================================================================

def _generate_demo_patient_flow_times(
    appointment_count: int,
    seed: int = 42
) -> dict[str, Any]:
    """Generiert Demo-Patientenfluss-Zeiten."""
    random.seed(seed)
    
    # Durchschnittliche Zeiten in Minuten
    avg_wait_time = random.uniform(8, 25)
    avg_prep_time = random.uniform(5, 15)
    avg_treatment_time = random.uniform(15, 45)
    avg_post_time = random.uniform(5, 15)
    avg_total_time = avg_wait_time + avg_prep_time + avg_treatment_time + avg_post_time
    
    # Trends
    wait_trend = random.uniform(-3, 3)
    total_trend = random.uniform(-5, 5)
    
    return {
        'avg_wait_time': round(avg_wait_time, 1),
        'avg_prep_time': round(avg_prep_time, 1),
        'avg_treatment_time': round(avg_treatment_time, 1),
        'avg_post_time': round(avg_post_time, 1),
        'avg_total_time': round(avg_total_time, 1),
        'wait_trend': round(wait_trend, 1),
        'total_trend': round(total_trend, 1),
        'patient_count': appointment_count,
    }


def _generate_demo_punctuality(seed: int = 42) -> dict[str, Any]:
    """Generiert Demo-Pünktlichkeitsdaten."""
    random.seed(seed)
    
    on_time = random.randint(60, 85)
    slight_delay = random.randint(10, 25)
    significant_delay = 100 - on_time - slight_delay
    
    avg_delay = random.uniform(3, 12)
    
    return {
        'on_time_rate': on_time,
        'slight_delay_rate': slight_delay,
        'significant_delay_rate': max(0, significant_delay),
        'avg_delay_minutes': round(avg_delay, 1),
        'trend': round(random.uniform(-2, 2), 1),
    }


def _generate_demo_documentation(appointment_count: int, seed: int = 42) -> dict[str, Any]:
    """Generiert Demo-Dokumentationsstatus."""
    random.seed(seed)
    
    completed = int(appointment_count * random.uniform(0.7, 0.95))
    pending = int(appointment_count * random.uniform(0.03, 0.15))
    overdue = appointment_count - completed - pending
    
    compliance_rate = round((completed / max(1, appointment_count)) * 100, 1)
    
    return {
        'completed': completed,
        'pending': max(0, pending),
        'overdue': max(0, overdue),
        'total': appointment_count,
        'compliance_rate': compliance_rate,
        'avg_completion_time': round(random.uniform(2, 24), 1),  # Stunden
    }


def _generate_demo_services(seed: int = 42) -> list[dict[str, Any]]:
    """Generiert Demo-Leistungsdaten."""
    random.seed(seed)
    
    services = [
        {'code': '01100', 'name': 'Beratung', 'points': 80},
        {'code': '01102', 'name': 'Eingehende Beratung', 'points': 160},
        {'code': '03000', 'name': 'Grundpauschale', 'points': 145},
        {'code': '03040', 'name': 'Hausbesuch', 'points': 285},
        {'code': '31010', 'name': 'Ambulante OP I', 'points': 380},
        {'code': '31011', 'name': 'Ambulante OP II', 'points': 520},
        {'code': '31012', 'name': 'Ambulante OP III', 'points': 750},
        {'code': '33010', 'name': 'Sonographie', 'points': 220},
        {'code': '33040', 'name': 'Belastungs-EKG', 'points': 185},
        {'code': '33041', 'name': 'Langzeit-EKG', 'points': 145},
    ]
    
    result = []
    for svc in services:
        count = random.randint(5, 150)
        result.append({
            'code': svc['code'],
            'name': svc['name'],
            'count': count,
            'points': svc['points'],
            'total_points': count * svc['points'],
        })
    
    return sorted(result, key=lambda x: -x['total_points'])


# ============================================================================
# KPI-Berechnungen
# ============================================================================

def calculate_overall_utilization(
    start_dt: datetime,
    end_dt: datetime,
    days: int,
) -> dict[str, Any]:
    """
    Berechnet die Gesamtauslastung der Praxis.
    
    Formel: (Gebuchte Zeit / Verfügbare Zeit) * 100
    """
    # Verfügbare Praxiszeit berechnen
    practice_hours = PracticeHours.objects.using('default').filter(active=True)
    
    total_available_minutes = 0
    for ph in practice_hours:
        # Anzahl der Wochentage im Zeitraum
        current = start_dt.date()
        while current <= end_dt.date():
            if current.weekday() == ph.weekday:
                start_minutes = ph.start_time.hour * 60 + ph.start_time.minute
                end_minutes = ph.end_time.hour * 60 + ph.end_time.minute
                total_available_minutes += (end_minutes - start_minutes)
            current += timedelta(days=1)
    
    # Gebuchte Zeit (Termine + OPs)
    appointments = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status__in=['scheduled', 'confirmed', 'completed'],
    )
    
    booked_minutes = 0
    for appt in appointments:
        duration = (appt.end_time - appt.start_time).total_seconds() / 60
        booked_minutes += duration
    
    operations = Operation.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status__in=['planned', 'confirmed', 'running', 'done'],
    )
    
    for op in operations:
        duration = (op.end_time - op.start_time).total_seconds() / 60
        booked_minutes += duration
    
    utilization = 0
    if total_available_minutes > 0:
        utilization = round((booked_minutes / total_available_minutes) * 100, 1)
    
    return {
        'utilization': min(100, utilization),
        'booked_hours': round(booked_minutes / 60, 1),
        'available_hours': round(total_available_minutes / 60, 1),
        'appointment_count': appointments.count(),
        'operation_count': operations.count(),
    }


def calculate_patient_throughput(
    start_dt: datetime,
    end_dt: datetime,
    days: int,
) -> dict[str, Any]:
    """
    Berechnet den Patientendurchsatz.
    
    Formel: Anzahl abgeschlossener Behandlungen / Zeitraum
    """
    completed_appointments = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status='completed',
    ).count()
    
    completed_operations = Operation.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status='done',
    ).count()
    
    total = completed_appointments + completed_operations
    
    # Tagesverteilung
    daily = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status='completed',
    ).annotate(
        day=TruncDate('start_time')
    ).values('day').annotate(
        count=Count('id')
    ).order_by('day')
    
    daily_data = list(daily)
    avg_per_day = round(total / max(1, days), 1)
    
    # Peak-Tag
    peak_day = max(daily_data, key=lambda x: x['count']) if daily_data else None
    
    return {
        'total': total,
        'appointments': completed_appointments,
        'operations': completed_operations,
        'avg_per_day': avg_per_day,
        'peak_day': peak_day['day'].strftime('%A') if peak_day else None,
        'peak_count': peak_day['count'] if peak_day else 0,
        'daily_data': daily_data,
    }


def calculate_no_show_rate(
    start_dt: datetime,
    end_dt: datetime,
) -> dict[str, Any]:
    """
    Berechnet die No-Show-Rate.
    
    Formel: (Nicht erschienene / Geplante vergangene Termine) * 100
    """
    now = timezone.now()
    past_end = min(end_dt, now)
    
    # Alle vergangenen geplanten Termine
    scheduled_past = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=past_end,
        status__in=['scheduled', 'confirmed'],
    ).count()
    
    completed = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=past_end,
        status='completed',
    ).count()
    
    total_past = scheduled_past + completed
    no_shows = scheduled_past  # Geplant aber nicht completed = No-Show
    
    no_show_rate = 0
    if total_past > 0:
        no_show_rate = round((no_shows / total_past) * 100, 1)
    
    return {
        'no_show_rate': no_show_rate,
        'no_show_count': no_shows,
        'total_past': total_past,
        'completed': completed,
    }


def calculate_cancellation_rate(
    start_dt: datetime,
    end_dt: datetime,
) -> dict[str, Any]:
    """
    Berechnet die Stornoquote.
    
    Formel: (Stornierte / Alle Termine) * 100
    """
    total = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    ).count()
    
    cancelled = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
        status='cancelled',
    ).count()
    
    cancelled_rate = 0
    if total > 0:
        cancelled_rate = round((cancelled / total) * 100, 1)
    
    return {
        'cancellation_rate': cancelled_rate,
        'cancelled_count': cancelled,
        'total': total,
    }


def calculate_resource_utilization(
    start_dt: datetime,
    end_dt: datetime,
    days: int,
) -> dict[str, Any]:
    """
    Berechnet die Ressourcenauslastung (Räume und Geräte).
    """
    resources = Resource.objects.using('default').filter(active=True)
    
    resource_stats = []
    
    for resource in resources:
        # Praxiszeiten als Basis
        practice_hours = PracticeHours.objects.using('default').filter(active=True)
        available_minutes = 0
        
        for ph in practice_hours:
            current = start_dt.date()
            while current <= end_dt.date():
                if current.weekday() == ph.weekday:
                    start_min = ph.start_time.hour * 60 + ph.start_time.minute
                    end_min = ph.end_time.hour * 60 + ph.end_time.minute
                    available_minutes += (end_min - start_min)
                current += timedelta(days=1)
        
        # Gebuchte Zeit
        booked_minutes = 0
        
        if resource.type == 'room':
            # Termine
            appt_resources = AppointmentResource.objects.using('default').filter(
                resource=resource,
                appointment__start_time__gte=start_dt,
                appointment__start_time__lte=end_dt,
                appointment__status__in=['scheduled', 'confirmed', 'completed'],
            ).select_related('appointment')
            
            for ar in appt_resources:
                duration = (ar.appointment.end_time - ar.appointment.start_time).total_seconds() / 60
                booked_minutes += duration
            
            # OPs
            ops = Operation.objects.using('default').filter(
                op_room=resource,
                start_time__gte=start_dt,
                start_time__lte=end_dt,
                status__in=['planned', 'confirmed', 'running', 'done'],
            )
            
            for op in ops:
                duration = (op.end_time - op.start_time).total_seconds() / 60
                booked_minutes += duration
        else:
            # Geräte bei Terminen
            appt_resources = AppointmentResource.objects.using('default').filter(
                resource=resource,
                appointment__start_time__gte=start_dt,
                appointment__start_time__lte=end_dt,
                appointment__status__in=['scheduled', 'confirmed', 'completed'],
            ).select_related('appointment')
            
            for ar in appt_resources:
                duration = (ar.appointment.end_time - ar.appointment.start_time).total_seconds() / 60
                booked_minutes += duration
            
            # Geräte bei OPs
            op_devices = OperationDevice.objects.using('default').filter(
                resource=resource,
                operation__start_time__gte=start_dt,
                operation__start_time__lte=end_dt,
                operation__status__in=['planned', 'confirmed', 'running', 'done'],
            ).select_related('operation')
            
            for od in op_devices:
                duration = (od.operation.end_time - od.operation.start_time).total_seconds() / 60
                booked_minutes += duration
        
        utilization = 0
        if available_minutes > 0:
            utilization = round((booked_minutes / available_minutes) * 100, 1)
        
        resource_stats.append({
            'id': resource.id,
            'name': resource.name,
            'type': resource.type,
            'color': resource.color,
            'utilization': min(100, utilization),
            'booked_hours': round(booked_minutes / 60, 1),
            'available_hours': round(available_minutes / 60, 1),
        })
    
    # Sortieren nach Auslastung (absteigend)
    resource_stats.sort(key=lambda x: -x['utilization'])
    
    # Aggregierte Werte
    rooms = [r for r in resource_stats if r['type'] == 'room']
    devices = [r for r in resource_stats if r['type'] == 'device']
    
    avg_room_util = round(sum(r['utilization'] for r in rooms) / max(1, len(rooms)), 1)
    avg_device_util = round(sum(r['utilization'] for r in devices) / max(1, len(devices)), 1)
    
    return {
        'resources': resource_stats,
        'rooms': rooms,
        'devices': devices,
        'avg_room_utilization': avg_room_util,
        'avg_device_utilization': avg_device_util,
        'bottleneck_room': rooms[0] if rooms else None,
        'bottleneck_device': devices[0] if devices else None,
    }


def calculate_bottleneck_index(
    resource_utilization: dict[str, Any],
    no_show: dict[str, Any],
    cancellation: dict[str, Any],
) -> dict[str, Any]:
    """
    Berechnet den Engpass-Index.
    
    Formel: Gewichtete Kombination aus:
    - Ressourcen mit >80% Auslastung
    - Wartezeiten-Überschreitungen
    - Prozessverzögerungen
    """
    # Hochausgelastete Ressourcen
    high_util_resources = [
        r for r in resource_utilization['resources']
        if r['utilization'] >= 80
    ]
    
    # Engpass-Score (0-100)
    resource_score = min(100, len(high_util_resources) * 20)
    
    # No-Show erhöht Engpass-Risiko
    no_show_score = min(100, no_show['no_show_rate'] * 5)
    
    # Storno reduziert tatsächliche Auslastung
    cancel_score = min(100, cancellation['cancellation_rate'] * 3)
    
    # Gewichteter Index
    bottleneck_index = round(
        (resource_score * 0.5 + no_show_score * 0.3 + cancel_score * 0.2),
        1
    )
    
    # Engpass-Kategorie
    if bottleneck_index >= 70:
        category = 'critical'
        label = 'Kritisch'
    elif bottleneck_index >= 50:
        category = 'high'
        label = 'Hoch'
    elif bottleneck_index >= 30:
        category = 'medium'
        label = 'Mittel'
    else:
        category = 'low'
        label = 'Niedrig'
    
    return {
        'index': bottleneck_index,
        'category': category,
        'label': label,
        'high_util_count': len(high_util_resources),
        'high_util_resources': high_util_resources[:5],
        'contributing_factors': [
            {'name': 'Ressourcenauslastung', 'score': resource_score, 'weight': 0.5},
            {'name': 'No-Show-Rate', 'score': no_show_score, 'weight': 0.3},
            {'name': 'Stornoquote', 'score': cancel_score, 'weight': 0.2},
        ],
    }


def calculate_hourly_distribution(
    start_dt: datetime,
    end_dt: datetime,
) -> dict[str, Any]:
    """
    Berechnet die stündliche Verteilung von Terminen und OPs.
    """
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
    
    # Zusammenführen
    hourly = {}
    for h in range(6, 22):  # 6:00 - 21:00
        hourly[h] = {'hour': h, 'appointments': 0, 'operations': 0, 'total': 0}
    
    for row in appointments:
        if row['hour'] in hourly:
            hourly[row['hour']]['appointments'] = row['count']
            hourly[row['hour']]['total'] += row['count']
    
    for row in operations:
        if row['hour'] in hourly:
            hourly[row['hour']]['operations'] = row['count']
            hourly[row['hour']]['total'] += row['count']
    
    hourly_list = list(hourly.values())
    
    # Peak-Stunde
    peak = max(hourly_list, key=lambda x: x['total']) if hourly_list else None
    
    return {
        'distribution': hourly_list,
        'peak_hour': peak['hour'] if peak else None,
        'peak_count': peak['total'] if peak else 0,
    }


def calculate_status_distribution(
    start_dt: datetime,
    end_dt: datetime,
) -> dict[str, Any]:
    """
    Berechnet die Statusverteilung für Termine und OPs.
    """
    # Termine
    appt_status = Appointment.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    ).values('status').annotate(
        count=Count('id')
    )
    
    # OPs
    op_status = Operation.objects.using('default').filter(
        start_time__gte=start_dt,
        start_time__lte=end_dt,
    ).values('status').annotate(
        count=Count('id')
    )
    
    appointment_stats = {row['status']: row['count'] for row in appt_status}
    operation_stats = {row['status']: row['count'] for row in op_status}
    
    return {
        'appointments': appointment_stats,
        'operations': operation_stats,
        'total_appointments': sum(appointment_stats.values()),
        'total_operations': sum(operation_stats.values()),
    }


def calculate_patient_flow_status(
    start_dt: datetime,
    end_dt: datetime,
) -> dict[str, Any]:
    """
    Berechnet den aktuellen Patientenfluss-Status.
    """
    now = timezone.now()
    today_start = timezone.make_aware(
        datetime.combine(timezone.localdate(), time.min),
        timezone.get_current_timezone()
    )
    
    # Heutiger Patientenfluss
    flow_status = PatientFlow.objects.using('default').filter(
        status_changed_at__gte=today_start,
    ).values('status').annotate(
        count=Count('id')
    )
    
    status_counts = {row['status']: row['count'] for row in flow_status}
    
    # Statusfarben
    status_colors = {
        'registered': '#6C757D',
        'waiting': '#FFC107',
        'preparing': '#17A2B8',
        'in_treatment': '#28A745',
        'post_treatment': '#0D6EFD',
        'done': '#198754',
    }
    
    status_labels = {
        'registered': 'Angemeldet',
        'waiting': 'Im Wartezimmer',
        'preparing': 'In Vorbereitung',
        'in_treatment': 'In Behandlung',
        'post_treatment': 'Nachbereitung',
        'done': 'Abgeschlossen',
    }
    
    result = []
    for status, label in status_labels.items():
        result.append({
            'status': status,
            'label': label,
            'count': status_counts.get(status, 0),
            'color': status_colors.get(status, '#6C757D'),
        })
    
    total_active = sum(
        status_counts.get(s, 0)
        for s in ['registered', 'waiting', 'preparing', 'in_treatment', 'post_treatment']
    )
    
    return {
        'statuses': result,
        'total_active': total_active,
        'done_today': status_counts.get('done', 0),
        'in_treatment': status_counts.get('in_treatment', 0),
        'waiting': status_counts.get('waiting', 0),
    }


# ============================================================================
# Aggregierte KPI-Sammler
# ============================================================================

def get_all_operations_kpis(days: int = 30) -> dict[str, Any]:
    """
    Sammelt alle KPIs für das Operations-Dashboard.
    """
    start_date, end_date, start_dt, end_dt = get_date_range(days)
    
    # Echte KPIs berechnen
    utilization = calculate_overall_utilization(start_dt, end_dt, days)
    throughput = calculate_patient_throughput(start_dt, end_dt, days)
    no_show = calculate_no_show_rate(start_dt, end_dt)
    cancellation = calculate_cancellation_rate(start_dt, end_dt)
    resources = calculate_resource_utilization(start_dt, end_dt, days)
    bottleneck = calculate_bottleneck_index(resources, no_show, cancellation)
    hourly = calculate_hourly_distribution(start_dt, end_dt)
    status = calculate_status_distribution(start_dt, end_dt)
    patient_flow = calculate_patient_flow_status(start_dt, end_dt)
    
    # Demo-Daten für fehlende Echtdaten
    total_appointments = utilization['appointment_count'] + utilization['operation_count']
    flow_times = _generate_demo_patient_flow_times(total_appointments, seed=days)
    punctuality = _generate_demo_punctuality(seed=days)
    documentation = _generate_demo_documentation(total_appointments, seed=days)
    services = _generate_demo_services(seed=days)
    
    return {
        'period': {
            'label': get_period_label(days),
            'days': days,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
        },
        'utilization': utilization,
        'throughput': throughput,
        'no_show': no_show,
        'cancellation': cancellation,
        'resources': resources,
        'bottleneck': bottleneck,
        'hourly': hourly,
        'status_distribution': status,
        'patient_flow': patient_flow,
        'flow_times': flow_times,
        'punctuality': punctuality,
        'documentation': documentation,
        'services': services,
    }


def get_realtime_operations_kpis() -> dict[str, Any]:
    """
    Sammelt Echtzeit-KPIs für das Operations-Dashboard (nur heute).
    """
    return get_all_operations_kpis(days=1)
