from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from praxi_backend.core.models import User

from .models import (
	Appointment,
	AppointmentResource,
	AppointmentType,
	DoctorAbsence,
	DoctorBreak,
	DoctorHours,
	Operation,
	OperationDevice,
	PracticeHours,
	Resource,
)


def iso_z(dt: datetime) -> str:
	value = dt.isoformat()
	return value.replace('+00:00', 'Z')


def ceil_dt_to_minutes(dt: datetime, minutes: int) -> datetime:
	if minutes <= 1:
		return dt
	if dt.second or dt.microsecond:
		dt = dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
	mod = dt.minute % minutes
	if mod == 0:
		return dt
	return dt + timedelta(minutes=(minutes - mod))


def doctor_display_name(doctor: User) -> str:
	return doctor.get_full_name() or getattr(doctor, 'username', str(doctor.id))


def get_active_doctors(*, exclude_doctor_id: int | None = None) -> list[User]:
	qs = User.objects.using('default').filter(is_active=True, role__name='doctor')
	if exclude_doctor_id is not None:
		qs = qs.exclude(id=exclude_doctor_id)
	return list(qs.order_by('id'))


def resolve_doctor(doctor_id: int) -> User | None:
	return (
		DoctorHours._meta.get_field('doctor')
		.related_model.objects.using('default')
		.filter(id=doctor_id)
		.first()
	)


def resolve_type(type_id: int | None) -> AppointmentType | None:
	if type_id is None:
		return None
	return AppointmentType.objects.using('default').filter(id=type_id).first()


@dataclass(frozen=True)
class Availability:
	available: bool
	reason: str | None


def _scan_day_for_slot(
	*,
	doctor: User,
	current_date: date,
	duration_minutes: int,
	now_local: datetime,
	start_date: date,
	type_obj: AppointmentType | None,
	resources: list[Resource] | None = None,
	limit: int,
) -> tuple[list[dict], dict]:
	"""Return (suggestions, diagnostics) for a single day.

	diagnostics keys:
	- has_hours
	- absent
	- blocked_by_break
	- blocked_by_busy
	"""
	weekday = current_date.weekday()  # 0=Mon .. 6=Sun
	practice_hours = list(
		PracticeHours.objects.using('default')
		.filter(weekday=weekday, active=True)
		.order_by('start_time', 'id')
	)
	doctor_hours = list(
		DoctorHours.objects.using('default')
		.filter(doctor=doctor, weekday=weekday, active=True)
		.order_by('start_time', 'id')
	)

	diagnostics = {
		'has_hours': bool(practice_hours and doctor_hours),
		'absent': False,
		'blocked_by_break': False,
		'blocked_by_busy': False,
		'blocked_by_resource': False,
	}
	if not diagnostics['has_hours']:
		return [], diagnostics

	absent = DoctorAbsence.objects.using('default').filter(
		doctor=doctor,
		active=True,
		start_date__lte=current_date,
		end_date__gte=current_date,
	).exists()
	diagnostics['absent'] = bool(absent)
	if absent:
		return [], diagnostics

	tz = timezone.get_current_timezone()
	day_start = timezone.make_aware(datetime.combine(current_date, time.min), tz)
	day_end_inclusive = timezone.make_aware(datetime.combine(current_date, time.max), tz)
	day_end_for_query = day_end_inclusive + timedelta(microseconds=1)

	existing = list(
		Appointment.objects.using('default')
		.filter(
			doctor=doctor,
			start_time__lt=day_end_for_query,
			end_time__gt=day_start,
		)
		.only('start_time', 'end_time')
		.order_by('start_time', 'id')
	)

	break_rows = list(
		DoctorBreak.objects.using('default')
		.filter(active=True, date=current_date)
		.filter(Q(doctor__isnull=True) | Q(doctor=doctor))
		.only('start_time', 'end_time', 'doctor_id')
		.order_by('start_time', 'doctor_id', 'id')
	)
	break_intervals = [
		(
			timezone.make_aware(datetime.combine(current_date, br.start_time), tz),
			timezone.make_aware(datetime.combine(current_date, br.end_time), tz),
		)
		for br in break_rows
	]

	resource_intervals: list[tuple[datetime, datetime]] = []
	resource_ids: list[int] = []
	resource_colors: list[str] = []
	if resources:
		resource_ids = [r.id for r in resources]
		resource_colors = [r.color for r in resources]

		resource_rows = list(
			AppointmentResource.objects.using('default')
			.filter(resource_id__in=resource_ids)
			.filter(
				appointment__start_time__lt=day_end_for_query,
				appointment__end_time__gt=day_start,
			)
			.select_related('appointment')
			.order_by('appointment__start_time', 'appointment_id', 'resource_id', 'id')
		)
		for ar in resource_rows:
			appt = ar.appointment
			resource_intervals.append((appt.start_time, appt.end_time))

		# Also block intervals where operations use any of the requested resources.
		room_ids = [r.id for r in resources if getattr(r, 'type', None) == 'room']
		if room_ids:
			op_rows = list(
				Operation.objects.using('default')
				.filter(
					op_room_id__in=room_ids,
					start_time__lt=day_end_for_query,
					end_time__gt=day_start,
				)
				.only('start_time', 'end_time')
				.order_by('start_time', 'id')
			)
			for op in op_rows:
				resource_intervals.append((op.start_time, op.end_time))

		device_ids = [r.id for r in resources if getattr(r, 'type', None) == 'device']
		if device_ids:
			od_rows = list(
				OperationDevice.objects.using('default')
				.filter(
					resource_id__in=device_ids,
					operation__start_time__lt=day_end_for_query,
					operation__end_time__gt=day_start,
				)
				.select_related('operation')
				.order_by('operation__start_time', 'operation_id', 'resource_id', 'id')
			)
			for od in od_rows:
				op = od.operation
				resource_intervals.append((op.start_time, op.end_time))

	def overlaps_any(candidate_start: datetime, candidate_end: datetime) -> bool:
		for appt in existing:
			if appt.start_time < candidate_end and appt.end_time > candidate_start:
				diagnostics['blocked_by_busy'] = True
				return True
		for br_start, br_end in break_intervals:
			if br_start < candidate_end and br_end > candidate_start:
				diagnostics['blocked_by_break'] = True
				return True
		for r_start, r_end in resource_intervals:
			if r_start < candidate_end and r_end > candidate_start:
				diagnostics['blocked_by_resource'] = True
				return True
		return False

	suggestions: list[dict] = []
	step = timedelta(minutes=5)
	duration = timedelta(minutes=duration_minutes)

	for ph in practice_hours:
		for dh in doctor_hours:
			window_start_t = max(ph.start_time, dh.start_time)
			window_end_t = min(ph.end_time, dh.end_time)
			if window_start_t >= window_end_t:
				continue

			window_start_dt = timezone.make_aware(datetime.combine(current_date, window_start_t), tz)
			window_end_dt = timezone.make_aware(datetime.combine(current_date, window_end_t), tz)

			candidate_base = window_start_dt
			# If suggestions start today, do not propose slots before current time.
			if start_date == now_local.date() and current_date == start_date:
				candidate_base = max(window_start_dt, now_local)

			candidate = ceil_dt_to_minutes(candidate_base, 5)
			latest_start = window_end_dt - duration

			while candidate <= latest_start and len(suggestions) < limit:
				candidate_end = candidate + duration
				if not overlaps_any(candidate, candidate_end):
					type_payload = (
						None
						if type_obj is None
						else {'id': type_obj.id, 'name': type_obj.name, 'color': type_obj.color}
					)
					suggestions.append(
						{
							'start_time': iso_z(candidate),
							'end_time': iso_z(candidate_end),
							'type': type_payload,
							'doctor_color': getattr(doctor, 'calendar_color', None),
							'type_color': getattr(type_obj, 'color', None) if type_obj is not None else None,
							'resource_ids': resource_ids,
							'resource_colors': resource_colors,
						}
					)
					break
				candidate = candidate + step

			if len(suggestions) >= limit:
				break
		if len(suggestions) >= limit:
			break

	return suggestions, diagnostics


def compute_suggestions_for_doctor(
	*,
	doctor: User,
	start_date: date,
	duration_minutes: int,
	limit: int,
	type_obj: AppointmentType | None,
	resources: list[Resource] | None = None,
	end_date: date | None = None,
	now: datetime | None = None,
	max_days: int = 366,
) -> list[dict]:
	"""Compute time-slot suggestions for a doctor.

	Returns list of dicts with keys: start_time, end_time, type.
	"""
	if duration_minutes <= 0 or limit <= 0:
		return []

	tz = timezone.get_current_timezone()
	now_local = timezone.localtime(now or timezone.now(), tz)

	suggestions: list[dict] = []
	days_checked = 0
	current_date = start_date

	while len(suggestions) < limit and days_checked < max_days:
		if end_date is not None and current_date > end_date:
			break

		day_suggestions, _diag = _scan_day_for_slot(
			doctor=doctor,
			current_date=current_date,
			duration_minutes=duration_minutes,
			now_local=now_local,
			start_date=start_date,
			type_obj=type_obj,
			resources=resources,
			limit=limit - len(suggestions),
		)
		suggestions.extend(day_suggestions)

		current_date = current_date + timedelta(days=1)
		days_checked += 1

	return suggestions


def availability_for_range(
	*,
	doctor: User,
	start_date: date,
	end_date: date,
	duration_minutes: int,
	max_days: int | None = None,
) -> Availability:
	"""Compute simple availability for calendar UI.

	Assumption: "available" means at least one free slot of given duration exists
	within [start_date, end_date].
	"""
	if end_date < start_date:
		return Availability(available=False, reason='no_hours')

	tz = timezone.get_current_timezone()
	now_local = timezone.localtime(timezone.now(), tz)

	days_checked = 0
	max_days = max_days if max_days is not None else (end_date - start_date).days + 1

	seen_hours_any = False
	seen_absence_on_hours_day = False
	seen_break_block = False
	seen_busy_block = False

	current_date = start_date
	while current_date <= end_date and days_checked < max_days:
		suggestions, diag = _scan_day_for_slot(
			doctor=doctor,
			current_date=current_date,
			duration_minutes=duration_minutes,
			now_local=now_local,
			start_date=start_date,
			type_obj=None,
			limit=1,
		)
		if diag['has_hours']:
			seen_hours_any = True
			if diag['absent']:
				seen_absence_on_hours_day = True
			else:
				seen_break_block = seen_break_block or diag['blocked_by_break']
				seen_busy_block = seen_busy_block or diag['blocked_by_busy']

		if suggestions:
			return Availability(available=True, reason=None)

		current_date = current_date + timedelta(days=1)
		days_checked += 1

	if not seen_hours_any:
		return Availability(available=False, reason='no_hours')
	if seen_absence_on_hours_day and not (seen_break_block or seen_busy_block):
		return Availability(available=False, reason='absence')
	if seen_break_block and not seen_busy_block:
		return Availability(available=False, reason='break')
	return Availability(available=False, reason='busy')
