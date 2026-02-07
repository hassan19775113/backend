"""
Scheduling KPIs - Kennzahlen für Terminplanung und Effizienz

KPI-Definitionen:
1. Slot Utilization Rate - Belegte vs. verfügbare Slots
2. No-Show Rate - Termine ohne Erscheinen (approximiert via cancelled/completed)
3. Cancellation Rate - Stornierte Termine
4. Average Lead Time - Zeit zwischen Buchung und Termin
5. Scheduling Efficiency Score - Ersttermin-Treffer vs. Umbuchungen
6. Rebooking Rate - Verschobene Termine (via updated_at > created_at + 1h)
7. New-Patient Conversion - Neue Patienten vs. Bestandspatienten
8. Peak-Load Analysis - Auslastung nach Wochentag/Uhrzeit
9. Behandler-/Raum-Kapazitätsauslastung - Theorie vs. Praxis
"""

from datetime import date, datetime, timedelta
from typing import Any

from django.db.models import Count, Min
from django.db.models.functions import ExtractHour, ExtractWeekDay
from django.utils import timezone
from praxi_backend.appointments.models import (
    Appointment,
    AppointmentResource,
    DoctorAbsence,
    DoctorHours,
    PracticeHours,
    Resource,
)
from praxi_backend.core.models import User


def get_scheduling_date_ranges() -> dict[str, tuple[datetime, datetime]]:
    """Datumsbereiche für Scheduling-KPIs."""
    tz = timezone.get_current_timezone()
    now = timezone.now()
    today_start = timezone.make_aware(datetime.combine(now.date(), datetime.min.time()), tz)
    today_end = timezone.make_aware(datetime.combine(now.date(), datetime.max.time()), tz)

    # Diese Woche
    week_start = today_start - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)

    # Dieser Monat
    month_start = today_start.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_month - timedelta(seconds=1)

    # Letzte 30 Tage
    last_30_start = today_start - timedelta(days=29)

    # Letzte 90 Tage (für Trends)
    last_90_start = today_start - timedelta(days=89)

    return {
        "today": (today_start, today_end),
        "week": (week_start, week_end),
        "month": (month_start, month_end),
        "last_30": (last_30_start, today_end),
        "last_90": (last_90_start, today_end),
    }


def calculate_available_slots(start_date: date, end_date: date) -> dict[str, Any]:
    """Berechnet verfügbare Slots basierend auf Practice/Doctor Hours."""
    # Praxis-Öffnungszeiten pro Wochentag
    practice_hours = list(
        PracticeHours.objects.using("default")
        .filter(active=True)
        .values("weekday", "start_time", "end_time")
    )

    # Ärzte mit Arbeitszeiten
    doctors = User.objects.using("default").filter(is_active=True, role__name="doctor")
    doctor_count = doctors.count()

    # Räume
    rooms = Resource.objects.using("default").filter(type="room", active=True).count()

    # Berechne Slots (angenommen 30min pro Slot)
    slot_duration_mins = 30
    total_available_mins = 0

    current = start_date
    while current <= end_date:
        weekday = current.weekday()

        # Praxis-Öffnungszeit an diesem Tag
        day_hours = [ph for ph in practice_hours if ph["weekday"] == weekday]

        for ph in day_hours:
            start = datetime.combine(current, ph["start_time"])
            end = datetime.combine(current, ph["end_time"])
            mins = (end - start).seconds // 60

            # Pro Arzt und Raum (limitierender Faktor)
            capacity_factor = min(doctor_count, rooms) if rooms > 0 else doctor_count
            total_available_mins += mins * capacity_factor

        current += timedelta(days=1)

    total_slots = total_available_mins // slot_duration_mins

    return {
        "total_slots": total_slots,
        "total_minutes": total_available_mins,
        "doctor_count": doctor_count,
        "room_count": rooms,
    }


def calculate_slot_utilization() -> dict[str, Any]:
    """Slot Utilization Rate - Belegte vs. verfügbare Slots."""
    ranges = get_scheduling_date_ranges()
    week_start, week_end = ranges["week"]

    # Verfügbare Slots
    available = calculate_available_slots(week_start.date(), week_end.date())

    # Gebuchte Termine (nicht storniert)
    booked = Appointment.objects.using("default").filter(
        start_time__gte=week_start,
        start_time__lte=week_end,
        status__in=["scheduled", "confirmed", "completed"],
    )

    booked_count = booked.count()
    booked_mins = sum((a.end_time - a.start_time).total_seconds() / 60 for a in booked)

    # Auslastungsrate
    if available["total_slots"] > 0:
        utilization_rate = round((booked_count / available["total_slots"]) * 100, 1)
    else:
        utilization_rate = 0

    # Trend (Vergleich mit Vorwoche)
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = week_end - timedelta(days=7)

    prev_booked = (
        Appointment.objects.using("default")
        .filter(
            start_time__gte=prev_week_start,
            start_time__lte=prev_week_end,
            status__in=["scheduled", "confirmed", "completed"],
        )
        .count()
    )

    if prev_booked > 0:
        trend = round(((booked_count - prev_booked) / prev_booked) * 100, 1)
    else:
        trend = 0

    return {
        "utilization_rate": utilization_rate,
        "booked_slots": booked_count,
        "available_slots": available["total_slots"],
        "booked_minutes": round(booked_mins, 0),
        "trend": trend,
        "trend_direction": "up" if trend > 0 else ("down" if trend < 0 else "neutral"),
    }


def calculate_no_show_rate() -> dict[str, Any]:
    """No-Show Rate - Approximiert durch nicht-completed Termine in der Vergangenheit."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges["last_30"]
    now = timezone.now()

    # Vergangene Termine (end_time < now)
    past_appointments = Appointment.objects.using("default").filter(
        end_time__lt=now,
        start_time__gte=last_30_start,
    )

    total = past_appointments.count()

    flagged_no_shows = past_appointments.filter(is_no_show=True).count()
    fallback_no_shows = past_appointments.filter(
        is_no_show=False, status__in=["scheduled", "confirmed"]
    ).count()
    no_shows = flagged_no_shows + fallback_no_shows

    if total > 0:
        no_show_rate = round((no_shows / total) * 100, 1)
    else:
        no_show_rate = 0

    # Trend (letzte 30 vs. vorherige 30 Tage)
    prev_30_start = last_30_start - timedelta(days=30)
    prev_30_end = last_30_start - timedelta(seconds=1)

    prev_past = Appointment.objects.using("default").filter(
        end_time__lt=prev_30_end,
        start_time__gte=prev_30_start,
    )
    prev_total = prev_past.count()
    prev_flagged = prev_past.filter(is_no_show=True).count()
    prev_fallback = prev_past.filter(is_no_show=False, status__in=["scheduled", "confirmed"]).count()
    prev_no_shows = prev_flagged + prev_fallback

    if prev_total > 0:
        prev_rate = (prev_no_shows / prev_total) * 100
        trend = round(no_show_rate - prev_rate, 1)
    else:
        trend = 0

    return {
        "no_show_rate": no_show_rate,
        "no_show_count": no_shows,
        "total_past_appointments": total,
        "trend": trend,
        "trend_direction": "down" if trend < 0 else ("up" if trend > 0 else "neutral"),
    }


def calculate_completion_rate() -> dict[str, Any]:
    """Completion Rate für die letzten 30 Tage."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges["last_30"]

    appointments = Appointment.objects.using("default").filter(
        start_time__gte=last_30_start,
        start_time__lte=last_30_end,
    )

    total = appointments.count()
    completed = appointments.filter(status="completed").count()
    rate = round((completed / total) * 100, 1) if total > 0 else 0

    return {
        "rate": rate,
        "completed": completed,
        "total": total,
    }


def calculate_cancellation_rate() -> dict[str, Any]:
    """Cancellation Rate - Stornierte Termine."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges["last_30"]

    total = (
        Appointment.objects.using("default")
        .filter(
            created_at__gte=last_30_start,
        )
        .count()
    )

    cancelled = (
        Appointment.objects.using("default")
        .filter(
            created_at__gte=last_30_start,
            status="cancelled",
        )
        .count()
    )

    if total > 0:
        cancellation_rate = round((cancelled / total) * 100, 1)
    else:
        cancellation_rate = 0

    # Nach Zeitpunkt der Stornierung
    # Früh (> 24h vorher) vs. Spät (< 24h vorher)
    now = timezone.now()
    late_cancellations = (
        Appointment.objects.using("default")
        .filter(
            created_at__gte=last_30_start,
            status="cancelled",
            start_time__lt=now + timedelta(hours=24),
        )
        .count()
    )

    early_cancellations = cancelled - late_cancellations

    return {
        "cancellation_rate": cancellation_rate,
        "cancelled_count": cancelled,
        "total_appointments": total,
        "early_cancellations": early_cancellations,
        "late_cancellations": late_cancellations,
    }


def calculate_average_lead_time() -> dict[str, Any]:
    """Average Lead Time - Zeit zwischen Buchung und Termin."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges["last_30"]

    appointments = (
        Appointment.objects.using("default")
        .filter(
            created_at__gte=last_30_start,
            status__in=["scheduled", "confirmed", "completed"],
        )
        .only("created_at", "start_time")
    )

    if not appointments.exists():
        return {
            "avg_lead_time_days": 0,
            "avg_lead_time_hours": 0,
            "min_lead_time_hours": 0,
            "max_lead_time_days": 0,
            "same_day_bookings": 0,
            "same_day_rate": 0,
        }

    lead_times = []
    same_day = 0

    for appt in appointments:
        delta = appt.start_time - appt.created_at
        hours = delta.total_seconds() / 3600
        lead_times.append(hours)

        if appt.start_time.date() == appt.created_at.date():
            same_day += 1

    avg_hours = sum(lead_times) / len(lead_times)

    return {
        "avg_lead_time_days": round(avg_hours / 24, 1),
        "avg_lead_time_hours": round(avg_hours, 1),
        "min_lead_time_hours": round(min(lead_times), 1),
        "max_lead_time_days": round(max(lead_times) / 24, 1),
        "same_day_bookings": same_day,
        "same_day_rate": round((same_day / len(lead_times)) * 100, 1),
    }


def calculate_average_duration() -> float:
    """Durchschnittliche Termindauer (Minuten) der letzten 30 Tage."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges["last_30"]

    appointments = (
        Appointment.objects.using("default")
        .filter(
            start_time__gte=last_30_start,
            end_time__lte=last_30_end,
            status__in=["scheduled", "confirmed", "completed"],
        )
        .only("start_time", "end_time")
    )

    if not appointments.exists():
        return 0

    total_minutes = 0
    count = 0
    for appt in appointments:
        if appt.start_time and appt.end_time:
            total_minutes += (appt.end_time - appt.start_time).total_seconds() / 60
            count += 1

    if count == 0:
        return 0

    return round(total_minutes / count, 1)


def calculate_rebooking_rate() -> dict[str, Any]:
    """Rebooking Rate - Verschobene Termine (updated_at >> created_at)."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges["last_30"]

    appointments = Appointment.objects.using("default").filter(
        created_at__gte=last_30_start,
    )

    total = appointments.count()

    # Umbuchung = updated_at mehr als 1 Stunde nach created_at
    rebooked = 0
    for appt in appointments:
        if appt.updated_at and appt.created_at:
            delta = appt.updated_at - appt.created_at
            if delta.total_seconds() > 3600:  # > 1 Stunde
                rebooked += 1

    if total > 0:
        rebooking_rate = round((rebooked / total) * 100, 1)
    else:
        rebooking_rate = 0

    return {
        "rebooking_rate": rebooking_rate,
        "rebooked_count": rebooked,
        "total_appointments": total,
    }


def calculate_scheduling_efficiency() -> dict[str, Any]:
    """Scheduling Efficiency Score - Kombination aus Metrics."""
    utilization = calculate_slot_utilization()
    no_show = calculate_no_show_rate()
    cancellation = calculate_cancellation_rate()
    rebooking = calculate_rebooking_rate()

    # Effizienz-Score (0-100)
    # Hohe Auslastung gut, niedrige No-Show/Cancellation/Rebooking gut
    base_score = utilization["utilization_rate"]

    # Abzüge
    no_show_penalty = no_show["no_show_rate"] * 0.5
    cancellation_penalty = cancellation["cancellation_rate"] * 0.3
    rebooking_penalty = rebooking["rebooking_rate"] * 0.2

    efficiency_score = max(
        0, min(100, base_score - no_show_penalty - cancellation_penalty - rebooking_penalty)
    )

    # Bewertung
    if efficiency_score >= 80:
        rating = "excellent"
        rating_label = "Exzellent"
        rating_color = "#34A853"
    elif efficiency_score >= 60:
        rating = "good"
        rating_label = "Gut"
        rating_color = "#1A73E8"
    elif efficiency_score >= 40:
        rating = "average"
        rating_label = "Durchschnitt"
        rating_color = "#FBBC05"
    else:
        rating = "poor"
        rating_label = "Verbesserungsbedarf"
        rating_color = "#EA4335"

    return {
        "efficiency_score": round(efficiency_score, 1),
        "rating": rating,
        "rating_label": rating_label,
        "rating_color": rating_color,
        "components": {
            "utilization": utilization["utilization_rate"],
            "no_show_penalty": round(no_show_penalty, 1),
            "cancellation_penalty": round(cancellation_penalty, 1),
            "rebooking_penalty": round(rebooking_penalty, 1),
        },
    }


def calculate_new_patient_conversion() -> dict[str, Any]:
    """New-Patient Conversion - Neue vs. Bestandspatienten."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges["last_30"]

    # Alle Termine im Zeitraum
    appointments = (
        Appointment.objects.using("default")
        .filter(
            start_time__gte=last_30_start,
            status__in=["scheduled", "confirmed", "completed"],
        )
        .values("patient_id")
    )

    total_appointments = appointments.count()

    if total_appointments == 0:
        return {
            "new_patient_rate": 0,
            "new_patients": 0,
            "returning_patients": 0,
            "total_appointments": 0,
        }

    # Patienten mit erstem Termin im Zeitraum
    patient_first_appointments = (
        Appointment.objects.using("default")
        .values("patient_id")
        .annotate(first_appt=Min("start_time"))
        .order_by("patient_id")
    )

    new_patients = 0
    returning_patients = 0

    for appt in appointments:
        pid = appt["patient_id"]
        first = patient_first_appointments.filter(patient_id=pid).order_by("patient_id").first()
        if first and first["first_appt"] >= last_30_start:
            new_patients += 1
        else:
            returning_patients += 1

    new_patient_rate = round((new_patients / total_appointments) * 100, 1)

    return {
        "new_patient_rate": new_patient_rate,
        "new_patients": new_patients,
        "returning_patients": returning_patients,
        "total_appointments": total_appointments,
    }


def calculate_peak_load_heatmap() -> dict[str, Any]:
    """Peak-Load Analysis - Heatmap nach Wochentag und Stunde."""
    ranges = get_scheduling_date_ranges()
    last_30_start, last_30_end = ranges["last_30"]

    # Termine nach Stunde und Wochentag
    appointments = (
        Appointment.objects.using("default")
        .filter(start_time__gte=last_30_start, start_time__lte=last_30_end)
        .annotate(hour=ExtractHour("start_time"), weekday=ExtractWeekDay("start_time"))
        .values("hour", "weekday")
        .annotate(count=Count("id"))
    )

    # Django WeekDay: 1=Sonntag, 2=Montag, ..., 7=Samstag
    # Konvertiere zu 0=Montag, 6=Sonntag
    django_to_python = {2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 1: 6}
    day_names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

    # 7x24 Matrix
    matrix = [[0 for _ in range(24)] for _ in range(7)]

    for row in appointments:
        py_day = django_to_python.get(row["weekday"], 0)
        hour = row["hour"]
        matrix[py_day][hour] = row["count"]

    # Peak finden
    max_count = 0
    peak_day = 0
    peak_hour = 9

    for day_idx in range(7):
        for hour in range(24):
            if matrix[day_idx][hour] > max_count:
                max_count = matrix[day_idx][hour]
                peak_day = day_idx
                peak_hour = hour

    return {
        "matrix": matrix,
        "day_names": day_names,
        "peak_day": day_names[peak_day],
        "peak_hour": peak_hour,
        "peak_count": max_count,
    }


def calculate_doctor_capacity_utilization() -> list[dict[str, Any]]:
    """Behandler-Kapazitätsauslastung."""
    ranges = get_scheduling_date_ranges()
    week_start, week_end = ranges["week"]

    doctors = (
        User.objects.using("default")
        .filter(is_active=True, role__name="doctor")
        .order_by("last_name", "first_name")
    )

    utilization = []

    for doctor in doctors:
        # Verfügbare Stunden
        doctor_hours = DoctorHours.objects.using("default").filter(doctor=doctor, active=True)
        weekly_available_mins = 0
        for dh in doctor_hours:
            start = datetime.combine(date.today(), dh.start_time)
            end = datetime.combine(date.today(), dh.end_time)
            weekly_available_mins += (end - start).seconds // 60

        # Abwesenheiten abziehen
        absences = DoctorAbsence.objects.using("default").filter(
            doctor=doctor,
            active=True,
            start_date__lte=week_end.date(),
            end_date__gte=week_start.date(),
        )
        absence_days = 0
        for absence in absences:
            start = max(absence.start_date, week_start.date())
            end = min(absence.end_date, week_end.date())
            absence_days += (end - start).days + 1

        # Gebuchte Zeit
        appointments = Appointment.objects.using("default").filter(
            doctor=doctor,
            start_time__gte=week_start,
            start_time__lte=week_end,
            status__in=["scheduled", "confirmed", "completed"],
        )
        booked_mins = sum((a.end_time - a.start_time).total_seconds() / 60 for a in appointments)

        # Anpassung für Abwesenheiten
        if absence_days > 0 and weekly_available_mins > 0:
            available_mins = weekly_available_mins * (5 - absence_days) / 5
        else:
            available_mins = weekly_available_mins

        if available_mins > 0:
            util_percent = min(round((booked_mins / available_mins) * 100, 1), 100)
        else:
            util_percent = 0

        utilization.append(
            {
                "id": doctor.id,
                "name": doctor.get_full_name() or doctor.username,
                "color": doctor.calendar_color,
                "available_mins": round(available_mins, 0),
                "booked_mins": round(booked_mins, 0),
                "utilization": util_percent,
                "appointments": appointments.count(),
            }
        )

    return sorted(utilization, key=lambda x: x["utilization"], reverse=True)


def calculate_room_capacity_utilization() -> list[dict[str, Any]]:
    """Raum-Kapazitätsauslastung."""
    ranges = get_scheduling_date_ranges()
    week_start, week_end = ranges["week"]

    rooms = Resource.objects.using("default").filter(type="room", active=True)

    # Praxis-Öffnungszeiten pro Woche
    practice_hours = PracticeHours.objects.using("default").filter(active=True)
    weekly_open_mins = 0
    for ph in practice_hours:
        start = datetime.combine(date.today(), ph.start_time)
        end = datetime.combine(date.today(), ph.end_time)
        weekly_open_mins += (end - start).seconds // 60

    utilization = []

    for room in rooms:
        # Termine in diesem Raum
        appointment_mins = 0
        ar_rows = (
            AppointmentResource.objects.using("default")
            .filter(
                resource=room,
                appointment__start_time__gte=week_start,
                appointment__start_time__lte=week_end,
                appointment__status__in=["scheduled", "confirmed", "completed"],
            )
            .select_related("appointment")
        )

        for ar in ar_rows:
            a = ar.appointment
            appointment_mins += (a.end_time - a.start_time).total_seconds() / 60

        if weekly_open_mins > 0:
            util_percent = min(round((appointment_mins / weekly_open_mins) * 100, 1), 100)
        else:
            util_percent = 0

        utilization.append(
            {
                "id": room.id,
                "name": room.name,
                "color": room.color,
                "available_mins": weekly_open_mins,
                "booked_mins": round(appointment_mins, 0),
                "utilization": util_percent,
                "appointments": ar_rows.count(),
            }
        )

    return sorted(utilization, key=lambda x: x["utilization"], reverse=True)


def get_scheduling_trends() -> dict[str, Any]:
    """Trends über die letzten 12 Wochen."""
    now = timezone.now()

    weeks = []
    for i in range(12):
        week_end = now - timedelta(weeks=i)
        week_start = week_end - timedelta(days=6)

        # Termine
        appointments = Appointment.objects.using("default").filter(
            start_time__gte=week_start,
            start_time__lt=week_end,
        )
        total = appointments.count()
        completed = appointments.filter(status="completed").count()
        cancelled = appointments.filter(status="cancelled").count()

        # No-Show (nicht completed und vergangen)
        no_show = appointments.filter(
            status__in=["scheduled", "confirmed"],
            end_time__lt=now,
        ).count()

        weeks.append(
            {
                "week": week_start.strftime("%d.%m"),
                "total": total,
                "completed": completed,
                "cancelled": cancelled,
                "no_show": no_show,
                "completion_rate": round((completed / total) * 100, 1) if total > 0 else 0,
            }
        )

    return {"weeks": list(reversed(weeks))}


def get_all_scheduling_kpis() -> dict[str, Any]:
    """Sammelt alle Scheduling-KPIs."""
    slot_utilization = calculate_slot_utilization()
    no_show = calculate_no_show_rate()
    cancellation = calculate_cancellation_rate()
    lead_time = calculate_average_lead_time()
    rebooking = calculate_rebooking_rate()
    efficiency = calculate_scheduling_efficiency()
    new_patient = calculate_new_patient_conversion()
    completion_rate = calculate_completion_rate()
    avg_duration = calculate_average_duration()

    # Template-friendly aliases for existing structures
    lead_time_display = {
        "avg_days": lead_time["avg_lead_time_days"],
        "min_days": round(lead_time["min_lead_time_hours"] / 24, 1),
        "max_days": lead_time["max_lead_time_days"],
    }
    new_patient_display = {
        "rate": new_patient["new_patient_rate"],
        "new_patient_count": new_patient["new_patients"],
        "total_appointments": new_patient["total_appointments"],
    }
    no_show_display = {
        "rate": no_show["no_show_rate"],
        "no_show": no_show["no_show_count"],
        "total": no_show["total_past_appointments"],
    }

    # Inject aliases into the original dicts for template compatibility
    lead_time.update(lead_time_display)
    new_patient.update(new_patient_display)

    return {
        "slot_utilization": slot_utilization,
        "no_show": no_show,
        "cancellation": cancellation,
        "lead_time": lead_time,
        "rebooking": rebooking,
        "efficiency": efficiency,
        "new_patient": new_patient,
        "peak_load": calculate_peak_load_heatmap(),
        "doctor_utilization": calculate_doctor_capacity_utilization(),
        "room_utilization": calculate_room_capacity_utilization(),
        "trends": get_scheduling_trends(),
        "generated_at": timezone.now().isoformat(),
        # Keys used directly in scheduling.html
        "efficiency_score": efficiency["efficiency_score"],
        "completion_rate": completion_rate,
        "no_show_rate": no_show_display,
        "avg_duration": avg_duration,
    }
