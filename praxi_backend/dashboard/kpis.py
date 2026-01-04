"""
KPI-Berechnungen für das Admin-Dashboard
"""
from datetime import date, datetime, timedelta
from typing import Any

from django.db import models
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import ExtractHour, ExtractWeekDay, TruncDate
from django.utils import timezone

from praxi_backend.core.models import User, Role
from praxi_backend.appointments.models import (
    Appointment,
    AppointmentType,
    Operation,
    OperationType,
    Resource,
    DoctorHours,
    PracticeHours,
)


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
    
    return {
        'today': (today_start, today_end),
        'week': (week_start, week_end),
        'month': (month_start, month_end),
        'last_30': (last_30_start, today_end),
    }


def calculate_trend(current: int, previous: int) -> dict[str, Any]:
    """Berechnet Trend-Indikator."""
    if previous == 0:
        if current > 0:
            return {'direction': 'up', 'percent': 100, 'icon': '↑'}
        return {'direction': 'neutral', 'percent': 0, 'icon': '→'}
    
    change = ((current - previous) / previous) * 100
    if change > 5:
        return {'direction': 'up', 'percent': round(change, 1), 'icon': '↑'}
    elif change < -5:
        return {'direction': 'down', 'percent': round(abs(change), 1), 'icon': '↓'}
    return {'direction': 'neutral', 'percent': round(abs(change), 1), 'icon': '→'}


def get_user_kpis() -> dict[str, Any]:
    """KPIs für Benutzer und Rollen."""
    total_users = User.objects.using('default').filter(is_active=True).count()
    total_doctors = User.objects.using('default').filter(
        is_active=True, role__name='doctor'
    ).count()
    total_assistants = User.objects.using('default').filter(
        is_active=True, role__name='assistant'
    ).count()
    total_admins = User.objects.using('default').filter(
        is_active=True, role__name='admin'
    ).count()
    
    return {
        'total_users': total_users,
        'total_doctors': total_doctors,
        'total_assistants': total_assistants,
        'total_admins': total_admins,
    }


def get_patient_count() -> int:
    """Patienten-Anzahl aus medical DB (falls verfügbar)."""
    try:
        from praxi_backend.medical.models import Patient
        count = Patient.objects.using('medical').count()
        if count:
            return count
    except Exception:
        pass

    # Fallback: use the best available signal from managed data.
    cache_count = 0
    appt_count = 0

    # local cache table (default DB)
    try:
        from praxi_backend.patients.models import Patient as PatientCache

        cache_count = int(PatientCache.objects.using('default').count())
    except Exception:
        cache_count = 0

    # unique patient_ids from appointments (default DB)
    try:
        appt_count = int(Appointment.objects.using('default').values('patient_id').distinct().count())
    except Exception:
        appt_count = 0

    return max(cache_count, appt_count)


def get_appointment_kpis() -> dict[str, Any]:
    """KPIs für Termine."""
    ranges = get_date_ranges()
    
    # Termine nach Zeitraum
    today_start, today_end = ranges['today']
    week_start, week_end = ranges['week']
    month_start, month_end = ranges['month']
    last_30_start, _ = ranges['last_30']
    
    appointments_today = Appointment.objects.using('default').filter(
        start_time__gte=today_start, start_time__lte=today_end
    ).count()
    
    appointments_week = Appointment.objects.using('default').filter(
        start_time__gte=week_start, start_time__lte=week_end
    ).count()
    
    appointments_month = Appointment.objects.using('default').filter(
        start_time__gte=month_start, start_time__lte=month_end
    ).count()
    
    # Status-Verteilung
    status_counts = dict(
        Appointment.objects.using('default')
        .filter(start_time__gte=last_30_start)
        .values('status')
        .annotate(count=Count('id'))
        .values_list('status', 'count')
    )
    
    # Durchschnittliche Terminlänge (in Minuten)
    avg_duration = Appointment.objects.using('default').filter(
        start_time__gte=last_30_start
    ).annotate(
        duration_mins=(
            models.F('end_time') - models.F('start_time')
        )
    ).aggregate(avg=Avg('duration_mins'))
    
    # Manuelle Berechnung
    appointments = Appointment.objects.using('default').filter(
        start_time__gte=last_30_start
    ).only('start_time', 'end_time')
    
    if appointments.exists():
        total_minutes = sum(
            (a.end_time - a.start_time).total_seconds() / 60
            for a in appointments
        )
        avg_duration_mins = round(total_minutes / appointments.count(), 1)
    else:
        avg_duration_mins = 0
    
    # Vergleich mit vorheriger Woche für Trend
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = week_end - timedelta(days=7)
    appointments_prev_week = Appointment.objects.using('default').filter(
        start_time__gte=prev_week_start, start_time__lte=prev_week_end
    ).count()
    
    trend = calculate_trend(appointments_week, appointments_prev_week)
    
    return {
        'today': appointments_today,
        'week': appointments_week,
        'month': appointments_month,
        'avg_duration_mins': avg_duration_mins,
        'status_counts': status_counts,
        'trend': trend,
    }


def get_operation_kpis() -> dict[str, Any]:
    """KPIs für Operationen."""
    ranges = get_date_ranges()
    today_start, today_end = ranges['today']
    week_start, week_end = ranges['week']
    month_start, month_end = ranges['month']
    
    ops_today = Operation.objects.using('default').filter(
        start_time__gte=today_start, start_time__lte=today_end
    ).count()
    
    ops_week = Operation.objects.using('default').filter(
        start_time__gte=week_start, start_time__lte=week_end
    ).count()
    
    ops_month = Operation.objects.using('default').filter(
        start_time__gte=month_start, start_time__lte=month_end
    ).count()
    
    # Status-Verteilung
    status_counts = dict(
        Operation.objects.using('default')
        .filter(start_time__gte=month_start)
        .values('status')
        .annotate(count=Count('id'))
        .values_list('status', 'count')
    )
    
    # Trend
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = week_end - timedelta(days=7)
    ops_prev_week = Operation.objects.using('default').filter(
        start_time__gte=prev_week_start, start_time__lte=prev_week_end
    ).count()
    
    trend = calculate_trend(ops_week, ops_prev_week)
    
    return {
        'today': ops_today,
        'week': ops_week,
        'month': ops_month,
        'status_counts': status_counts,
        'trend': trend,
    }


def get_resource_kpis() -> dict[str, Any]:
    """KPIs für Ressourcen (Räume & Geräte)."""
    rooms = Resource.objects.using('default').filter(type='room', active=True)
    devices = Resource.objects.using('default').filter(type='device', active=True)
    
    return {
        'total_rooms': rooms.count(),
        'total_devices': devices.count(),
        'rooms': list(rooms.values('id', 'name', 'color')),
        'devices': list(devices.values('id', 'name', 'color')),
    }


def calculate_doctor_utilization() -> list[dict[str, Any]]:
    """Berechnet Arzt-Auslastung basierend auf Terminen."""
    ranges = get_date_ranges()
    week_start, week_end = ranges['week']
    
    doctors = User.objects.using('default').filter(
        is_active=True, role__name='doctor'
    ).order_by('last_name', 'first_name')
    
    utilization = []
    for doctor in doctors:
        # Geplante Stunden aus DoctorHours
        doctor_hours = DoctorHours.objects.using('default').filter(
            doctor=doctor, active=True
        )
        weekly_available_mins = 0
        for dh in doctor_hours:
            start = datetime.combine(date.today(), dh.start_time)
            end = datetime.combine(date.today(), dh.end_time)
            weekly_available_mins += (end - start).seconds // 60
        
        # Gebuchte Minuten aus Appointments
        appointments = Appointment.objects.using('default').filter(
            doctor=doctor,
            start_time__gte=week_start,
            start_time__lte=week_end,
            status__in=['scheduled', 'confirmed', 'completed']
        )
        booked_mins = sum(
            (a.end_time - a.start_time).total_seconds() / 60
            for a in appointments
        )
        
        # Auslastung berechnen
        if weekly_available_mins > 0:
            util_percent = min(round((booked_mins / weekly_available_mins) * 100, 1), 100)
        else:
            util_percent = 0
        
        utilization.append({
            'id': doctor.id,
            'name': doctor.get_full_name() or doctor.username,
            'color': doctor.calendar_color,
            'available_mins': weekly_available_mins,
            'booked_mins': round(booked_mins, 1),
            'utilization': util_percent,
        })
    
    return sorted(utilization, key=lambda x: x['utilization'], reverse=True)


def calculate_room_utilization() -> list[dict[str, Any]]:
    """Berechnet Raum-Auslastung."""
    ranges = get_date_ranges()
    week_start, week_end = ranges['week']
    
    rooms = Resource.objects.using('default').filter(type='room', active=True)
    
    # Praxis-Öffnungszeiten pro Woche
    practice_hours = PracticeHours.objects.using('default').filter(active=True)
    weekly_open_mins = 0
    for ph in practice_hours:
        start = datetime.combine(date.today(), ph.start_time)
        end = datetime.combine(date.today(), ph.end_time)
        weekly_open_mins += (end - start).seconds // 60
    
    utilization = []
    for room in rooms:
        # Termine in diesem Raum
        from praxi_backend.appointments.models import AppointmentResource
        appointment_mins = 0
        ar_rows = AppointmentResource.objects.using('default').filter(
            resource=room,
            appointment__start_time__gte=week_start,
            appointment__start_time__lte=week_end,
        ).select_related('appointment')
        for ar in ar_rows:
            a = ar.appointment
            appointment_mins += (a.end_time - a.start_time).total_seconds() / 60
        
        # OPs in diesem Raum
        ops = Operation.objects.using('default').filter(
            op_room=room,
            start_time__gte=week_start,
            start_time__lte=week_end,
        )
        op_mins = sum((o.end_time - o.start_time).total_seconds() / 60 for o in ops)
        
        total_booked = appointment_mins + op_mins
        
        if weekly_open_mins > 0:
            util_percent = min(round((total_booked / weekly_open_mins) * 100, 1), 100)
        else:
            util_percent = 0
        
        utilization.append({
            'id': room.id,
            'name': room.name,
            'color': room.color,
            'booked_mins': round(total_booked, 1),
            'utilization': util_percent,
        })
    
    return sorted(utilization, key=lambda x: x['utilization'], reverse=True)


def get_peak_hours() -> dict[str, Any]:
    """Analysiert Peak-Stunden für Termine."""
    ranges = get_date_ranges()
    last_30_start, last_30_end = ranges['last_30']
    
    # Termine nach Stunde gruppieren
    hourly = (
        Appointment.objects.using('default')
        .filter(start_time__gte=last_30_start, start_time__lte=last_30_end)
        .annotate(hour=ExtractHour('start_time'))
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('hour')
    )
    
    hourly_dict = {h['hour']: h['count'] for h in hourly}
    
    # Peak-Stunde finden
    if hourly_dict:
        peak_hour = max(hourly_dict, key=hourly_dict.get)
        peak_count = hourly_dict[peak_hour]
    else:
        peak_hour = 9
        peak_count = 0
    
    return {
        'hourly': hourly_dict,
        'peak_hour': peak_hour,
        'peak_count': peak_count,
    }


def get_peak_days() -> dict[str, Any]:
    """Analysiert Peak-Wochentage für Termine."""
    ranges = get_date_ranges()
    last_30_start, last_30_end = ranges['last_30']
    
    # Termine nach Wochentag gruppieren (Django: 1=Sonntag, 7=Samstag)
    daily = (
        Appointment.objects.using('default')
        .filter(start_time__gte=last_30_start, start_time__lte=last_30_end)
        .annotate(weekday=ExtractWeekDay('start_time'))
        .values('weekday')
        .annotate(count=Count('id'))
        .order_by('weekday')
    )
    
    # Konvertiere zu 0=Montag, 6=Sonntag
    day_names = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']
    django_to_python = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
    
    daily_dict = {day_names[i]: 0 for i in range(7)}
    for d in daily:
        python_day = django_to_python.get(d['weekday'], 0)
        daily_dict[day_names[python_day]] = d['count']
    
    # Peak-Tag finden
    if any(daily_dict.values()):
        peak_day = max(daily_dict, key=daily_dict.get)
        peak_count = daily_dict[peak_day]
    else:
        peak_day = 'Mo'
        peak_count = 0
    
    return {
        'daily': daily_dict,
        'peak_day': peak_day,
        'peak_count': peak_count,
    }


def get_all_kpis() -> dict[str, Any]:
    """Sammelt alle KPIs für das Dashboard."""
    return {
        'users': get_user_kpis(),
        'patients': get_patient_count(),
        'appointments': get_appointment_kpis(),
        'operations': get_operation_kpis(),
        'resources': get_resource_kpis(),
        'doctor_utilization': calculate_doctor_utilization(),
        'room_utilization': calculate_room_utilization(),
        'peak_hours': get_peak_hours(),
        'peak_days': get_peak_days(),
        'generated_at': timezone.now().isoformat(),
    }
