"""HTML calendar views for appointments (no JS).

These views render a Fluent/Outlook-style day calendar where appointments are
positioned in a time raster.

Note: This is a dashboard (staff-only) UI layer. The canonical calendar API
lives under `praxi_backend.appointments.views`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from calendar import monthrange

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.db.models.query import QuerySet
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from praxi_backend.appointments.models import Appointment
from praxi_backend.core.models import User


@dataclass(frozen=True)
class _CalendarConfig:
	px_per_min: int = 2
	slot_minutes: int = 30
	min_visible_minutes: int = 4 * 60
	pad_minutes: int = 30


def _parse_date(value: str | None, *, default: date) -> date:
	if not value:
		return default
	try:
		return date.fromisoformat(value)
	except Exception:
		return default


def _floor_to(minutes: int, step: int) -> int:
	return (minutes // step) * step


def _ceil_to(minutes: int, step: int) -> int:
	return ((minutes + step - 1) // step) * step


def _fmt_hhmm(total_minutes: int) -> str:
	h = total_minutes // 60
	m = total_minutes % 60
	return f"{h:02d}:{m:02d}"


def _status_label(status: str) -> tuple[str, str]:
	"""Return (label_de, key) for template classes."""
	mapping = {
		Appointment.STATUS_SCHEDULED: ("Geplant", "scheduled"),
		Appointment.STATUS_CONFIRMED: ("Bestätigt", "confirmed"),
		Appointment.STATUS_CANCELLED: ("Storniert", "cancelled"),
		Appointment.STATUS_COMPLETED: ("Abgeschlossen", "completed"),
	}
	return mapping.get(status, (status, "scheduled"))


def _doctor_display_name(user: User) -> str:
	return (user.get_full_name() or getattr(user, "username", "") or str(user.id)).strip()


def _parse_doctor_filters(request) -> tuple[str, int | None]:
	doctor_query = (request.GET.get("doctor") or "").strip()
	doctor_id_raw = (request.GET.get("doctor_id") or "").strip()
	selected_doctor_id: int | None = None
	try:
		if doctor_id_raw:
			selected_doctor_id = int(doctor_id_raw)
	except Exception:
		selected_doctor_id = None
	return doctor_query, selected_doctor_id


def _doctors_base_qs() -> QuerySet[User]:
	return User.objects.using("default").filter(is_active=True, role__name="doctor")


def _doctors_for_query(*, doctor_query: str) -> QuerySet[User]:
	qs = _doctors_base_qs()
	if doctor_query:
		qs = qs.filter(
			Q(first_name__icontains=doctor_query)
			| Q(last_name__icontains=doctor_query)
			| Q(username__icontains=doctor_query)
			| Q(email__icontains=doctor_query)
		)
	return qs.order_by("last_name", "first_name", "username", "id")


def _unique_doctor_items(*, doctors_qs, limit: int = 60) -> list[dict]:
	"""Return doctors as [{id, name}] but with unique display names.

	The UI requirement is: each displayed doctor name should appear only once.
	If multiple users share the same display name, we keep the first one by ordering.
	"""
	seen: set[str] = set()
	items: list[dict] = []
	for d in list(doctors_qs[: max(1, limit * 3)]):
		name = _doctor_display_name(d)
		key = name.casefold()
		if not name or key in seen:
			continue
		seen.add(key)
		items.append({"id": d.id, "name": name})
		if len(items) >= limit:
			break
	return items


class AppointmentCalendarDayView(View):
	"""Staff-only day calendar HTML view.

	GET /praxiadmin/dashboard/appointments/?date=YYYY-MM-DD
	"""

	@method_decorator(staff_member_required)
	def get(self, request):
		cfg = _CalendarConfig()
		tz = timezone.get_current_timezone()
		day = _parse_date(request.GET.get("date"), default=timezone.localdate())

		doctor_query, selected_doctor_id = _parse_doctor_filters(request)
		doctors_qs = _doctors_for_query(doctor_query=doctor_query)
		selected_doctor = None
		if selected_doctor_id is not None:
			# Resolve selected doctor from full base set (even if current query filters them out).
			selected_doctor = _doctors_base_qs().filter(id=selected_doctor_id).first()

		day_start = timezone.make_aware(datetime.combine(day, time.min), tz)
		day_end_inclusive = timezone.make_aware(datetime.combine(day, time.max), tz)
		day_end = day_end_inclusive + timedelta(microseconds=1)

		appt_qs = (
			Appointment.objects.using("default")
			.select_related("doctor", "type")
			.filter(start_time__lt=day_end, end_time__gt=day_start)
		)
		if selected_doctor_id is not None:
			appt_qs = appt_qs.filter(doctor_id=selected_doctor_id)
		elif doctor_query:
			matching_ids = list(doctors_qs.values_list("id", flat=True)[:250])
			if matching_ids:
				appt_qs = appt_qs.filter(doctor_id__in=matching_ids)
			else:
				appt_qs = appt_qs.none()

		rows = list(appt_qs.order_by("start_time", "id"))

		# Determine visible time range from appointments (local time).
		if rows:
			mins = []
			for appt in rows:
				start_local = timezone.localtime(appt.start_time, tz)
				end_local = timezone.localtime(appt.end_time, tz)
				mins.append(start_local.hour * 60 + start_local.minute)
				mins.append(end_local.hour * 60 + end_local.minute)

			min_start = min(mins)
			max_end = max(mins)

			start_min = _floor_to(min_start, cfg.slot_minutes) - cfg.pad_minutes
			end_min = _ceil_to(max_end, cfg.slot_minutes) + cfg.pad_minutes
			start_min = max(0, start_min)
			end_min = min(24 * 60, end_min)

			if end_min - start_min < cfg.min_visible_minutes:
				end_min = min(24 * 60, start_min + cfg.min_visible_minutes)
		else:
			# Sensible default when no appointments exist.
			start_min = 8 * 60
			end_min = 18 * 60

		grid_minutes = max(1, end_min - start_min)
		grid_height_px = grid_minutes * cfg.px_per_min

		time_slots: list[dict] = []
		m = start_min
		while m <= end_min:
			time_slots.append(
				{
					"label": _fmt_hhmm(m),
					"is_hour": (m % 60) == 0,
					"top_px": (m - start_min) * cfg.px_per_min,
				}
			)
			m += cfg.slot_minutes

		appointments: list[dict] = []
		for appt in rows:
			start_local = timezone.localtime(appt.start_time, tz)
			end_local = timezone.localtime(appt.end_time, tz)
			start_m = start_local.hour * 60 + start_local.minute
			end_m = end_local.hour * 60 + end_local.minute
			duration_m = max(1, end_m - start_m)

			top_px = (start_m - start_min) * cfg.px_per_min
			height_px = max(28, duration_m * cfg.px_per_min)

			label_de, status_key = _status_label(appt.status)
			doctor_name = appt.doctor.get_full_name() or getattr(appt.doctor, "username", str(appt.doctor_id))
			type_name = appt.type.name if appt.type else "Termin"

			accent = None
			try:
				accent = getattr(appt.type, "color", None) or getattr(appt.doctor, "calendar_color", None)
			except Exception:
				accent = None
			accent = accent or "#0078D4"

			appointments.append(
				{
					"id": appt.id,
					"patient_id": appt.patient_id,
					"doctor": doctor_name,
					"type": type_name,
					"status": label_de,
					"status_key": status_key,
					"time_range": f"{start_local:%H:%M}–{end_local:%H:%M}",
					"top_px": top_px,
					"height_px": height_px,
					"accent": accent,
				}
			)

		context = {
			"title": "Termine – Kalender",
			"day": day,
			"day_display": day.strftime("%d.%m.%Y"),
			"week_start": (day - timedelta(days=day.weekday())),
			"month_start": day.replace(day=1),
			"doctor_query": doctor_query,
			"selected_doctor_id": selected_doctor_id,
			"selected_doctor_name": (
				(_doctor_display_name(selected_doctor))
				if selected_doctor is not None
				else ""
			),
			"doctors": _unique_doctor_items(doctors_qs=doctors_qs, limit=60),
			"start_min": start_min,
			"end_min": end_min,
			"grid_height_px": grid_height_px,
			"slot_px": cfg.slot_minutes * cfg.px_per_min,
			"hour_px": 60 * cfg.px_per_min,
			"time_slots": time_slots,
			"appointments": appointments,
		}

		return render(request, "dashboard/appointments_calendar_day.html", context)


def _range_for_rows(
	*,
	tz,
	rows: list[Appointment],
	cfg: _CalendarConfig,
	default_start_min: int = 8 * 60,
	default_end_min: int = 18 * 60,
) -> tuple[int, int]:
	"""Compute a shared (start_min, end_min) window from a list of appointments."""
	if rows:
		mins: list[int] = []
		for appt in rows:
			start_local = timezone.localtime(appt.start_time, tz)
			end_local = timezone.localtime(appt.end_time, tz)
			mins.append(start_local.hour * 60 + start_local.minute)
			mins.append(end_local.hour * 60 + end_local.minute)

		min_start = min(mins)
		max_end = max(mins)

		start_min = _floor_to(min_start, cfg.slot_minutes) - cfg.pad_minutes
		end_min = _ceil_to(max_end, cfg.slot_minutes) + cfg.pad_minutes
		start_min = max(0, start_min)
		end_min = min(24 * 60, end_min)

		if end_min - start_min < cfg.min_visible_minutes:
			end_min = min(24 * 60, start_min + cfg.min_visible_minutes)
		return start_min, end_min

	return default_start_min, default_end_min


def _build_time_slots(*, start_min: int, end_min: int, cfg: _CalendarConfig) -> list[dict]:
	time_slots: list[dict] = []
	m = start_min
	while m <= end_min:
		time_slots.append(
			{
				"label": _fmt_hhmm(m),
				"is_hour": (m % 60) == 0,
				"top_px": (m - start_min) * cfg.px_per_min,
			}
		)
		m += cfg.slot_minutes
	return time_slots


def _event_payload(
	*,
	appt: Appointment,
	tz,
	start_min: int,
	cfg: _CalendarConfig,
) -> dict:
	start_local = timezone.localtime(appt.start_time, tz)
	end_local = timezone.localtime(appt.end_time, tz)
	start_m = start_local.hour * 60 + start_local.minute
	end_m = end_local.hour * 60 + end_local.minute
	duration_m = max(1, end_m - start_m)

	top_px = (start_m - start_min) * cfg.px_per_min
	height_px = max(28, duration_m * cfg.px_per_min)

	label_de, status_key = _status_label(appt.status)
	doctor_name = appt.doctor.get_full_name() or getattr(appt.doctor, "username", str(appt.doctor_id))
	type_name = appt.type.name if appt.type else "Termin"

	accent = None
	try:
		accent = getattr(appt.type, "color", None) or getattr(appt.doctor, "calendar_color", None)
	except Exception:
		accent = None
	accent = accent or "#0078D4"

	return {
		"id": appt.id,
		"patient_id": appt.patient_id,
		"doctor": doctor_name,
		"type": type_name,
		"status": label_de,
		"status_key": status_key,
		"time_range": f"{start_local:%H:%M}–{end_local:%H:%M}",
		"top_px": top_px,
		"height_px": height_px,
		"accent": accent,
		"start_iso": start_local.isoformat(),
		"day": start_local.date(),
	}


class AppointmentCalendarWeekView(View):
	"""Staff-only week calendar HTML view (no JS).

	GET /praxiadmin/dashboard/appointments/week/?date=YYYY-MM-DD
	"""

	@method_decorator(staff_member_required)
	def get(self, request):
		cfg = _CalendarConfig()
		tz = timezone.get_current_timezone()
		anchor = _parse_date(request.GET.get("date"), default=timezone.localdate())
		doctor_query, selected_doctor_id = _parse_doctor_filters(request)
		doctors_qs = _doctors_for_query(doctor_query=doctor_query)
		selected_doctor = None
		if selected_doctor_id is not None:
			selected_doctor = _doctors_base_qs().filter(id=selected_doctor_id).first()

		week_start = anchor - timedelta(days=anchor.weekday())
		week_end = week_start + timedelta(days=6)

		start_dt = timezone.make_aware(datetime.combine(week_start, time.min), tz)
		end_dt_inclusive = timezone.make_aware(datetime.combine(week_end, time.max), tz)
		end_dt = end_dt_inclusive + timedelta(microseconds=1)

		appt_qs = (
			Appointment.objects.using("default")
			.select_related("doctor", "type")
			.filter(start_time__lt=end_dt, end_time__gt=start_dt)
		)
		if selected_doctor_id is not None:
			appt_qs = appt_qs.filter(doctor_id=selected_doctor_id)
		elif doctor_query:
			matching_ids = list(doctors_qs.values_list("id", flat=True)[:250])
			if matching_ids:
				appt_qs = appt_qs.filter(doctor_id__in=matching_ids)
			else:
				appt_qs = appt_qs.none()

		rows = list(appt_qs.order_by("start_time", "id"))

		start_min, end_min = _range_for_rows(tz=tz, rows=rows, cfg=cfg)
		grid_minutes = max(1, end_min - start_min)
		grid_height_px = grid_minutes * cfg.px_per_min
		time_slots = _build_time_slots(start_min=start_min, end_min=end_min, cfg=cfg)

		# Group events by local day.
		events_by_day: dict[date, list[dict]] = {week_start + timedelta(days=i): [] for i in range(7)}
		for appt in rows:
			evt = _event_payload(appt=appt, tz=tz, start_min=start_min, cfg=cfg)
			day_key = evt["day"]
			if day_key in events_by_day:
				events_by_day[day_key].append(evt)

		week_days: list[dict] = []
		weekday_names = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
		for i in range(7):
			d = week_start + timedelta(days=i)
			week_days.append(
				{
					"date": d,
					"label": f"{weekday_names[i]} {d:%d.%m}",
					"iso": d.isoformat(),
					"is_today": d == timezone.localdate(),
					"events": events_by_day.get(d, []),
				}
			)

		context = {
			"title": "Termine – Woche",
			"anchor": anchor,
			"week_start": week_start,
			"week_end": week_end,
			"week_display": f"{week_start:%d.%m.%Y} – {week_end:%d.%m.%Y}",
			"prev_week": (week_start - timedelta(days=7)).isoformat(),
			"next_week": (week_start + timedelta(days=7)).isoformat(),
			"month_start": anchor.replace(day=1),
			"doctor_query": doctor_query,
			"selected_doctor_id": selected_doctor_id,
			"selected_doctor_name": (_doctor_display_name(selected_doctor) if selected_doctor else ""),
			"doctors": _unique_doctor_items(doctors_qs=doctors_qs, limit=60),
			"start_min": start_min,
			"end_min": end_min,
			"grid_height_px": grid_height_px,
			"slot_px": cfg.slot_minutes * cfg.px_per_min,
			"hour_px": 60 * cfg.px_per_min,
			"time_slots": time_slots,
			"week_days": week_days,
		}

		return render(request, "dashboard/appointments_calendar_week.html", context)


class AppointmentCalendarMonthView(View):
	"""Staff-only month calendar HTML view (no JS).

	GET /praxiadmin/dashboard/appointments/month/?date=YYYY-MM-DD
	"""

	@method_decorator(staff_member_required)
	def get(self, request):
		tz = timezone.get_current_timezone()
		anchor = _parse_date(request.GET.get("date"), default=timezone.localdate())
		doctor_query, selected_doctor_id = _parse_doctor_filters(request)
		doctors_qs = _doctors_for_query(doctor_query=doctor_query)
		selected_doctor = None
		if selected_doctor_id is not None:
			selected_doctor = _doctors_base_qs().filter(id=selected_doctor_id).first()

		month_start = anchor.replace(day=1)
		_days_in_month = monthrange(month_start.year, month_start.month)[1]
		month_end = month_start.replace(day=_days_in_month)

		# Build a full weeks grid (Mon..Sun) covering the whole month.
		grid_start = month_start - timedelta(days=month_start.weekday())
		grid_end = month_end + timedelta(days=(6 - month_end.weekday()))

		start_dt = timezone.make_aware(datetime.combine(grid_start, time.min), tz)
		end_dt_inclusive = timezone.make_aware(datetime.combine(grid_end, time.max), tz)
		end_dt = end_dt_inclusive + timedelta(microseconds=1)

		appt_qs = (
			Appointment.objects.using("default")
			.select_related("doctor", "type")
			.filter(start_time__lt=end_dt, end_time__gt=start_dt)
		)
		if selected_doctor_id is not None:
			appt_qs = appt_qs.filter(doctor_id=selected_doctor_id)
		elif doctor_query:
			matching_ids = list(doctors_qs.values_list("id", flat=True)[:250])
			if matching_ids:
				appt_qs = appt_qs.filter(doctor_id__in=matching_ids)
			else:
				appt_qs = appt_qs.none()

		rows = list(appt_qs.order_by("start_time", "id"))

		# Group by local day.
		events_by_day: dict[date, list[dict]] = {}
		for appt in rows:
			start_local = timezone.localtime(appt.start_time, tz)
			d = start_local.date()
			label_de, status_key = _status_label(appt.status)
			doctor_name = appt.doctor.get_full_name() or getattr(appt.doctor, "username", str(appt.doctor_id))
			type_name = appt.type.name if appt.type else "Termin"
			accent = getattr(appt.type, "color", None) or getattr(appt.doctor, "calendar_color", None) or "#0078D4"
			evt = {
				"id": appt.id,
				"patient_id": appt.patient_id,
				"doctor": doctor_name,
				"type": type_name,
				"status": label_de,
				"status_key": status_key,
				"time": f"{start_local:%H:%M}",
				"accent": accent,
				"day": d,
			}
			events_by_day.setdefault(d, []).append(evt)

		weeks: list[list[dict]] = []
		cur = grid_start
		today = timezone.localdate()
		while cur <= grid_end:
			week: list[dict] = []
			for _ in range(7):
				in_month = (cur.month == month_start.month)
				day_events = events_by_day.get(cur, [])
				week.append(
					{
						"date": cur,
						"iso": cur.isoformat(),
						"day": cur.day,
						"in_month": in_month,
						"is_today": cur == today,
						"events": day_events[:4],
						"more_count": max(0, len(day_events) - 4),
					}
				)
				cur = cur + timedelta(days=1)
			weeks.append(week)

		prev_month = (month_start - timedelta(days=1)).replace(day=1)
		next_month = (month_end + timedelta(days=1)).replace(day=1)

		context = {
			"title": "Termine – Monat",
			"anchor": anchor,
			"month_start": month_start,
			"month_end": month_end,
			"month_display": month_start.strftime("%B %Y"),
			"prev_month": prev_month.isoformat(),
			"next_month": next_month.isoformat(),
			"doctor_query": doctor_query,
			"selected_doctor_id": selected_doctor_id,
			"selected_doctor_name": (_doctor_display_name(selected_doctor) if selected_doctor else ""),
			"doctors": _unique_doctor_items(doctors_qs=doctors_qs, limit=60),
			"weeks": weeks,
			"weekday_labels": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
		}

		return render(request, "dashboard/appointments_calendar_month.html", context)
