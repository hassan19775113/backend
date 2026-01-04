import calendar
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.response import Response

from praxi_backend.core.utils import log_patient_action

from .models import (
	Appointment,
	AppointmentResource,
	AppointmentType,
	DoctorAbsence,
	DoctorBreak,
	DoctorHours,
	Operation,
	OperationDevice,
	OperationType,
	PatientFlow,
	PracticeHours,
	Resource,
)
from .scheduling import (
	availability_for_range,
	compute_suggestions_for_doctor,
	doctor_display_name,
	get_active_doctors,
	resolve_doctor,
)
from .exceptions import (
	DoctorAbsentError,
	DoctorBreakConflict,
	InvalidSchedulingData,
	SchedulingConflictError,
	SchedulingError,
	WorkingHoursViolation,
)
from .services.scheduling import (
	plan_appointment as scheduling_plan_appointment,
	plan_operation as scheduling_plan_operation,
)
from .permissions import (
	AppointmentPermission,
	AppointmentSuggestPermission,
	AppointmentTypePermission,
	DoctorAbsencePermission,
	DoctorBreakPermission,
	DoctorHoursPermission,
	OperationPermission,
	OperationSuggestPermission,
	OperationTypePermission,
	OpDashboardPermission,
	OpStatsPermission,
	OpTimelinePermission,
	ResourceCalendarPermission,
	PatientFlowPermission,
	PracticeHoursPermission,
	ResourcePermission,
)
from .serializers import (
		ResourceCalendarColumnSerializer,
		PatientFlowCreateUpdateSerializer,
		PatientFlowSerializer,
		PatientFlowStatusUpdateSerializer,
	AppointmentCreateUpdateSerializer,
	AppointmentSerializer,
	AppointmentTypeSerializer,
	DoctorAbsenceSerializer,
	DoctorBreakSerializer,
	DoctorHoursSerializer,
	OperationCreateUpdateSerializer,
	OperationDashboardSerializer,
	OperationSerializer,
	OperationTypeSerializer,
	OpTimelineGroupSerializer,
	OPStatsDeviceSerializer,
	OPStatsOverviewSerializer,
	OPStatsRoomSerializer,
	OPStatsSurgeonSerializer,
	OPStatsTypeSerializer,
		RoomTimelineSerializer,
	PracticeHoursSerializer,
	ResourceSerializer,
)


def _parse_stats_range(request):
	"""Parse ?date=YYYY-MM-DD OR ?from=YYYY-MM-DD&to=YYYY-MM-DD.

	Returns (start_dt, end_dt_inclusive, start_date, end_date, err_response)
	"""
	date_str = request.query_params.get('date')
	from_str = request.query_params.get('from')
	to_str = request.query_params.get('to')

	def _parse_date(value: str):
		return datetime.strptime(value, '%Y-%m-%d').date()

	try:
		if date_str:
			d = _parse_date(date_str)
			start_date = d
			end_date = d
		elif from_str and to_str:
			start_date = _parse_date(from_str)
			end_date = _parse_date(to_str)
			if start_date > end_date:
				return None, None, None, None, Response(
					{'detail': 'from must be <= to.'},
					status=status.HTTP_400_BAD_REQUEST,
				)
		else:
			return None, None, None, None, Response(
				{'detail': 'Provide either ?date=YYYY-MM-DD or ?from=YYYY-MM-DD&to=YYYY-MM-DD.'},
				status=status.HTTP_400_BAD_REQUEST,
			)
	except ValueError:
		return None, None, None, None, Response(
			{'detail': 'Dates must be in format YYYY-MM-DD.'},
			status=status.HTTP_400_BAD_REQUEST,
		)

	tz = timezone.get_current_timezone()
	start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
	end_dt = timezone.make_aware(datetime.combine(end_date, time.max), tz)
	return start_dt, end_dt, start_date, end_date, None


def _default_room_total_minutes(*, start_date: date, end_date: date) -> int:
	# Default opening time: 08:00–16:00 (8 hours) per day.
	days = (end_date - start_date).days + 1
	return max(0, int(days) * 8 * 60)


class _OpStatsBaseView(generics.GenericAPIView):
	permission_classes = [OpStatsPermission]
	stats_scope: str = ''

	def _ops_queryset(self, request, start_dt: datetime, end_dt_inclusive: datetime):
		# inclusive end via +1 microsecond and __lt
		end_for_query = end_dt_inclusive + timedelta(microseconds=1)
		qs = Operation.objects.using('default').filter(
			start_time__lt=end_for_query,
			end_time__gt=start_dt,
		)
		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			# Doctors only see their own operations for allowed endpoints.
			qs = qs.filter(
				Q(primary_surgeon=request.user)
				| Q(assistant=request.user)
				| Q(anesthesist=request.user)
			)
		return qs.select_related('op_type', 'op_room', 'primary_surgeon', 'assistant', 'anesthesist')

	def _audit(self, request, *, start_date: date, end_date: date):
		log_patient_action(
			request.user,
			'op_stats_view',
			meta={
				'scope': self.stats_scope,
				'from': start_date.isoformat(),
				'to': end_date.isoformat(),
			},
		)


class OpStatsOverviewView(_OpStatsBaseView):
	stats_scope = 'overview'
	serializer_class = OPStatsOverviewSerializer

	def get(self, request, *args, **kwargs):
		start_dt, end_dt, start_date, end_date, err = _parse_stats_range(request)
		if err is not None:
			return err

		ops = list(self._ops_queryset(request, start_dt, end_dt).order_by('start_time', 'id'))
		durations = []
		for op in ops:
			minutes = int(max(0, (op.end_time - op.start_time).total_seconds() // 60))
			durations.append(minutes)

		total_minutes = int(sum(durations))
		count = int(len(durations))
		avg = float(total_minutes / count) if count else 0.0

		payload = {
			'range_from': start_date,
			'range_to': end_date,
			'op_count': count,
			'total_op_minutes': total_minutes,
			'average_op_duration': avg,
		}
		self._audit(request, start_date=start_date, end_date=end_date)
		return Response(self.get_serializer(payload).data, status=status.HTTP_200_OK)


class OpStatsRoomsView(_OpStatsBaseView):
	stats_scope = 'rooms'
	serializer_class = OPStatsRoomSerializer

	def get(self, request, *args, **kwargs):
		start_dt, end_dt, start_date, end_date, err = _parse_stats_range(request)
		if err is not None:
			return err

		total_minutes = _default_room_total_minutes(start_date=start_date, end_date=end_date)
		ops = list(self._ops_queryset(request, start_dt, end_dt).order_by('start_time', 'id'))

		used_by_room: dict[int, int] = {}
		rooms: dict[int, Resource] = {}
		for op in ops:
			room = op.op_room
			if room is None:
				continue
			rooms[room.id] = room
			minutes = int(max(0, (op.end_time - op.start_time).total_seconds() // 60))
			used_by_room[room.id] = used_by_room.get(room.id, 0) + minutes

		items = []
		for room_id in sorted(rooms.keys()):
			used = int(used_by_room.get(room_id, 0))
			util = float(used / total_minutes) if total_minutes else 0.0
			items.append(
				{
					'room': ResourceSerializer(rooms[room_id]).data,
					'total_minutes': total_minutes,
					'used_minutes': used,
					'utilization': util,
				}
			)

		self._audit(request, start_date=start_date, end_date=end_date)
		return Response(
			{
				'range_from': start_date.isoformat(),
				'range_to': end_date.isoformat(),
				'rooms': self.get_serializer(items, many=True).data,
			},
			status=status.HTTP_200_OK,
		)


class OpStatsDevicesView(_OpStatsBaseView):
	stats_scope = 'devices'
	serializer_class = OPStatsDeviceSerializer

	def get(self, request, *args, **kwargs):
		start_dt, end_dt, start_date, end_date, err = _parse_stats_range(request)
		if err is not None:
			return err

		ops = list(self._ops_queryset(request, start_dt, end_dt).order_by('start_time', 'id'))
		if not ops:
			self._audit(request, start_date=start_date, end_date=end_date)
			return Response(
				{
					'range_from': start_date.isoformat(),
					'range_to': end_date.isoformat(),
					'devices': [],
				},
				status=status.HTTP_200_OK,
			)

		op_ids = [o.id for o in ops]
		row_qs = (
			OperationDevice.objects.using('default')
			.filter(operation_id__in=op_ids)
			.select_related('resource', 'operation')
			.order_by('resource_id', 'operation_id', 'id')
		)

		usage: dict[int, int] = {}
		devices: dict[int, Resource] = {}
		for row in row_qs:
			dev = row.resource
			devices[dev.id] = dev
			op = row.operation
			minutes = int(max(0, (op.end_time - op.start_time).total_seconds() // 60))
			usage[dev.id] = usage.get(dev.id, 0) + minutes

		items = []
		for dev_id in sorted(devices.keys()):
			items.append(
				{
					'device': ResourceSerializer(devices[dev_id]).data,
					'usage_minutes': int(usage.get(dev_id, 0)),
				}
			)

		self._audit(request, start_date=start_date, end_date=end_date)
		return Response(
			{
				'range_from': start_date.isoformat(),
				'range_to': end_date.isoformat(),
				'devices': self.get_serializer(items, many=True).data,
			},
			status=status.HTTP_200_OK,
		)


class OpStatsSurgeonsView(_OpStatsBaseView):
	stats_scope = 'surgeons'
	serializer_class = OPStatsSurgeonSerializer

	def get(self, request, *args, **kwargs):
		start_dt, end_dt, start_date, end_date, err = _parse_stats_range(request)
		if err is not None:
			return err

		ops_qs = self._ops_queryset(request, start_dt, end_dt)
		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			# Do not leak other surgeons even if the doctor assisted.
			ops_qs = ops_qs.filter(primary_surgeon=request.user)

		ops = list(ops_qs.order_by('start_time', 'id'))
		by: dict[int, dict] = {}
		for op in ops:
			surgeon = op.primary_surgeon
			if surgeon is None:
				continue
			key = surgeon.id
			entry = by.get(key)
			if entry is None:
				entry = {
					'surgeon': {
						'id': surgeon.id,
						'name': doctor_display_name(surgeon),
						'color': getattr(surgeon, 'calendar_color', None),
					},
					'op_count': 0,
					'total_op_minutes': 0,
				}
				by[key] = entry
			minutes = int(max(0, (op.end_time - op.start_time).total_seconds() // 60))
			entry['op_count'] += 1
			entry['total_op_minutes'] += minutes

		items = []
		for key in sorted(by.keys()):
			entry = by[key]
			count = int(entry['op_count'])
			total = int(entry['total_op_minutes'])
			entry['average_op_duration'] = float(total / count) if count else 0.0
			items.append(entry)

		self._audit(request, start_date=start_date, end_date=end_date)
		return Response(
			{
				'range_from': start_date.isoformat(),
				'range_to': end_date.isoformat(),
				'surgeons': self.get_serializer(items, many=True).data,
			},
			status=status.HTTP_200_OK,
		)


class OpStatsTypesView(_OpStatsBaseView):
	stats_scope = 'types'
	serializer_class = OPStatsTypeSerializer

	def get(self, request, *args, **kwargs):
		start_dt, end_dt, start_date, end_date, err = _parse_stats_range(request)
		if err is not None:
			return err

		ops = list(self._ops_queryset(request, start_dt, end_dt).order_by('start_time', 'id'))
		by: dict[int, dict] = {}
		for op in ops:
			t = op.op_type
			if t is None:
				continue
			key = t.id
			minutes = int(max(0, (op.end_time - op.start_time).total_seconds() // 60))
			entry = by.get(key)
			if entry is None:
				entry = {
					'type': {'id': t.id, 'name': t.name, 'color': t.color},
					'_durations': [],
				}
				by[key] = entry
			entry['_durations'].append(minutes)

		items = []
		for key in sorted(by.keys()):
			entry = by[key]
			durations = entry.pop('_durations')
			count = int(len(durations))
			total = int(sum(durations))
			items.append(
				{
					'type': entry['type'],
					'count': count,
					'avg_duration': float(total / count) if count else 0.0,
					'min_duration': int(min(durations)) if durations else 0,
					'max_duration': int(max(durations)) if durations else 0,
				}
			)

		self._audit(request, start_date=start_date, end_date=end_date)
		return Response(
			{
				'range_from': start_date.isoformat(),
				'range_to': end_date.isoformat(),
				'types': self.get_serializer(items, many=True).data,
			},
			status=status.HTTP_200_OK,
		)


def _parse_required_date(request):
	date_str = request.query_params.get('date')
	if not date_str:
		return None, Response({'detail': 'Provide ?date=YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)
	try:
		d = datetime.strptime(date_str, '%Y-%m-%d').date()
		return d, None
	except ValueError:
		return None, Response({'detail': 'Date must be in format YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)


class _OpTimelineBaseView(generics.GenericAPIView):
	permission_classes = [OpTimelinePermission]
	serializer_class = OpTimelineGroupSerializer

	def _ops_for_date(self, request, day: date):
		qs = Operation.objects.using('default').filter(start_time__date=day)
		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			qs = qs.filter(
				Q(primary_surgeon=request.user)
				| Q(assistant=request.user)
				| Q(anesthesist=request.user)
			)
		return qs.select_related('op_type', 'op_room', 'primary_surgeon', 'assistant', 'anesthesist')

	def _ops_for_live(self, request):
		now = timezone.now()
		threshold = now - timedelta(minutes=30)
		qs = Operation.objects.using('default').filter(
			status__in=[Operation.STATUS_RUNNING, Operation.STATUS_CONFIRMED],
			start_time__gte=threshold,
		)
		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			qs = qs.filter(
				Q(primary_surgeon=request.user)
				| Q(assistant=request.user)
				| Q(anesthesist=request.user)
			)
		return qs.select_related('op_type', 'op_room', 'primary_surgeon', 'assistant', 'anesthesist')

	def _group_by_room(self, ops):
		groups: dict[int, dict] = {}
		for op in ops:
			room = getattr(op, 'op_room', None)
			if room is None:
				continue
			entry = groups.get(room.id)
			if entry is None:
				entry = {'room': room, 'operations': []}
				groups[room.id] = entry
			entry['operations'].append(op)

		# Sort rooms by name, and ops by start_time inside each room.
		result = sorted(groups.values(), key=lambda e: (getattr(e['room'], 'name', ''), getattr(e['room'], 'id', 0)))
		for e in result:
			e['operations'].sort(key=lambda o: (getattr(o, 'start_time', None), getattr(o, 'id', 0)))
		return result

	def _audit(self, request, *, day: date | None = None, live: bool = False):
		meta = {'live': bool(live)}
		if day is not None:
			meta['date'] = day.isoformat()
		log_patient_action(request.user, 'op_timeline_view', meta=meta)


class OpTimelineView(_OpTimelineBaseView):
	"""GET /api/op-timeline/?date=YYYY-MM-DD"""

	def get(self, request, *args, **kwargs):
		day, err = _parse_required_date(request)
		if err is not None:
			return err
		ops = list(self._ops_for_date(request, day).order_by('op_room__name', 'start_time', 'id'))
		payload = self._group_by_room(ops)
		self._audit(request, day=day)
		return Response(self.get_serializer(payload, many=True).data, status=status.HTTP_200_OK)


class OpTimelineRoomsView(generics.GenericAPIView):
	"""GET /api/op-timeline/rooms/?date=YYYY-MM-DD

	Returns all rooms with their (visible) operations on that date.
	For doctors, rooms without visible operations may appear with operations=[].
	"""

	permission_classes = [OpTimelinePermission]
	serializer_class = OpTimelineGroupSerializer

	def get(self, request, *args, **kwargs):
		day, err = _parse_required_date(request)
		if err is not None:
			return err

		rooms = list(
			Resource.objects.using('default')
			.filter(type=Resource.TYPE_ROOM, active=True)
			.order_by('name', 'id')
		)

		qs = Operation.objects.using('default').filter(start_time__date=day)
		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			qs = qs.filter(
				Q(primary_surgeon=request.user)
				| Q(assistant=request.user)
				| Q(anesthesist=request.user)
			)
		ops = list(
			qs.select_related('op_type', 'op_room', 'primary_surgeon', 'assistant', 'anesthesist')
			.order_by('start_time', 'id')
		)

		ops_by_room: dict[int, list] = {}
		for op in ops:
			rid = getattr(op, 'op_room_id', None)
			if rid is None:
				continue
			ops_by_room.setdefault(int(rid), []).append(op)

		payload = [{'room': r, 'operations': ops_by_room.get(r.id, [])} for r in rooms]
		log_patient_action(request.user, 'op_timeline_view', meta={'rooms': True, 'date': day.isoformat()})
		return Response(self.get_serializer(payload, many=True).data, status=status.HTTP_200_OK)


class OpTimelineLiveView(_OpTimelineBaseView):
	"""GET /api/op-timeline/live/"""

	def get(self, request, *args, **kwargs):
		ops = list(self._ops_for_live(request).order_by('op_room__name', 'start_time', 'id'))
		payload = self._group_by_room(ops)
		self._audit(request, live=True)
		return Response(self.get_serializer(payload, many=True).data, status=status.HTTP_200_OK)


def _parse_resource_ids(request):
	value = request.query_params.get('resource_ids')
	if not value:
		return None, Response({'detail': 'Provide resource_ids as comma-separated list.'}, status=status.HTTP_400_BAD_REQUEST)
	try:
		ids = [int(x) for x in value.split(',') if x.strip()]
	except ValueError:
		return None, Response({'detail': 'resource_ids must be integers.'}, status=status.HTTP_400_BAD_REQUEST)
	if not ids:
		return None, Response({'detail': 'resource_ids cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)
	# de-dup while preserving order
	seen = set()
	out = []
	for i in ids:
		if i not in seen:
			seen.add(i)
			out.append(i)
	return out, None


def _booking_status_for_operation(op: Operation):
	st = getattr(op, 'status', None)
	if st == Operation.STATUS_RUNNING:
		return 'running'
	if st in (Operation.STATUS_PLANNED, Operation.STATUS_CONFIRMED):
		return 'planned'
	return None


class ResourceCalendarResourcesView(generics.GenericAPIView):
	"""GET /api/resource-calendar/resources/

	- admin/assistant/billing: alle Ressourcen (rooms + devices)
	- doctor: nur Ressourcen, die er in Terminen/OPs nutzt
	"""

	permission_classes = [ResourceCalendarPermission]
	serializer_class = ResourceSerializer

	def get(self, request, *args, **kwargs):
		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		qs = Resource.objects.using('default').filter(active=True)
		if role_name != 'doctor':
			resources = list(qs.order_by('type', 'name', 'id'))
			log_patient_action(request.user, 'resource_calendar_view', meta={'resources': True})
			return Response(self.get_serializer(resources, many=True).data, status=status.HTTP_200_OK)

		# Doctor: resources used by their appointments and operations.
		appt_res_ids = (
			AppointmentResource.objects.using('default')
			.filter(appointment__doctor=request.user)
			.values_list('resource_id', flat=True)
			.distinct()
		)
		op_qs = Operation.objects.using('default').filter(
			Q(primary_surgeon=request.user)
			| Q(assistant=request.user)
			| Q(anesthesist=request.user)
		)
		op_room_ids = op_qs.values_list('op_room_id', flat=True).distinct()
		op_ids = list(op_qs.values_list('id', flat=True))
		device_ids = []
		if op_ids:
			device_ids = list(
				OperationDevice.objects.using('default')
				.filter(operation_id__in=op_ids)
				.values_list('resource_id', flat=True)
				.distinct()
			)
		allowed_ids = set(list(appt_res_ids) + list(op_room_ids) + list(device_ids))
		resources = list(qs.filter(id__in=allowed_ids).order_by('type', 'name', 'id'))
		log_patient_action(request.user, 'resource_calendar_view', meta={'resources': True})
		return Response(self.get_serializer(resources, many=True).data, status=status.HTTP_200_OK)


class ResourceCalendarView(generics.GenericAPIView):
	"""GET /api/resource-calendar/?date=YYYY-MM-DD&resource_ids=1,2,3"""

	permission_classes = [ResourceCalendarPermission]
	serializer_class = ResourceCalendarColumnSerializer

	def get(self, request, *args, **kwargs):
		day, err = _parse_required_date(request)
		if err is not None:
			return err
		resource_ids, err2 = _parse_resource_ids(request)
		if err2 is not None:
			return err2

		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		tz = timezone.get_current_timezone()
		range_start = timezone.make_aware(datetime.combine(day, time.min), tz)
		range_end = timezone.make_aware(datetime.combine(day, time.max), tz)
		range_end_for_query = range_end + timedelta(microseconds=1)

		# Resource columns requested
		resources = list(
			Resource.objects.using('default')
			.filter(id__in=resource_ids, active=True)
			.order_by('type', 'name', 'id')
		)
		resource_by_id = {r.id: r for r in resources}
		ordered_resources = [resource_by_id[i] for i in resource_ids if i in resource_by_id]

		# Optional: for doctor, restrict to resources they actually use.
		# Note: We intentionally keep the requested resource columns.
		# RBAC is applied on bookings (appointments/operations/absences/breaks).

		# Bookings collected per resource_id
		bookings: dict[int, list[dict]] = {r.id: [] for r in ordered_resources}
		if not ordered_resources:
			log_patient_action(request.user, 'resource_calendar_view', meta={'date': day.isoformat()})
			return Response([], status=status.HTTP_200_OK)

		selected_ids = [r.id for r in ordered_resources]

		# 1) Appointments via AppointmentResource
		ar_qs = (
			AppointmentResource.objects.using('default')
			.filter(
				resource_id__in=selected_ids,
				appointment__start_time__lt=range_end_for_query,
				appointment__end_time__gt=range_start,
			)
			.select_related('appointment', 'appointment__type', 'appointment__doctor')
			.order_by('appointment__start_time', 'appointment_id', 'resource_id', 'id')
		)
		if role_name == 'doctor':
			ar_qs = ar_qs.filter(appointment__doctor=request.user)

		for ar in ar_qs:
			appt = ar.appointment
			label = 'Termin'
			type_obj = getattr(appt, 'type', None)
			if type_obj is not None and getattr(type_obj, 'name', None):
				label = str(type_obj.name)
			doctor = getattr(appt, 'doctor', None)
			if doctor is not None:
				label = f"{label} – {doctor_display_name(doctor)}"
			color = getattr(type_obj, 'color', None) if type_obj is not None else None
			if color is None and doctor is not None:
				color = getattr(doctor, 'calendar_color', None)

			bookings[ar.resource_id].append(
				{
					'kind': 'appointment',
					'id': appt.id,
					'start_time': appt.start_time,
					'end_time': appt.end_time,
					'color': color,
					'label': label,
					'status': None,
				}
			)

		# 2) Operations (rooms)
		op_qs = Operation.objects.using('default').filter(
			start_time__lt=range_end_for_query,
			end_time__gt=range_start,
		)
		if role_name == 'doctor':
			op_qs = op_qs.filter(
				Q(primary_surgeon=request.user)
				| Q(assistant=request.user)
				| Q(anesthesist=request.user)
			)
		op_qs = op_qs.select_related('op_type', 'op_room', 'primary_surgeon').order_by('start_time', 'id')
		for op in op_qs:
			room_id = getattr(op, 'op_room_id', None)
			if room_id in bookings:
				t = getattr(op, 'op_type', None)
				primary = getattr(op, 'primary_surgeon', None)
				label = 'OP'
				if t is not None and getattr(t, 'name', None):
					label = str(t.name)
				if primary is not None:
					label = f"{label} – {doctor_display_name(primary)}"
				bookings[room_id].append(
					{
						'kind': 'operation',
						'id': op.id,
						'start_time': op.start_time,
						'end_time': op.end_time,
						'color': getattr(t, 'color', None) if t is not None else None,
						'label': label,
						'status': _booking_status_for_operation(op),
						'progress': OperationDashboardSerializer().get_progress(op),
					}
				)

		# 3) Operations (devices)
		# Query operation_devices only for selected device resources
		device_rows = (
			OperationDevice.objects.using('default')
			.filter(resource_id__in=selected_ids)
			.select_related('operation', 'operation__op_type', 'operation__primary_surgeon')
			.filter(operation__start_time__lt=range_end_for_query, operation__end_time__gt=range_start)
			.order_by('operation__start_time', 'operation_id', 'resource_id', 'id')
		)
		if role_name == 'doctor':
			device_rows = device_rows.filter(
				Q(operation__primary_surgeon=request.user)
				| Q(operation__assistant=request.user)
				| Q(operation__anesthesist=request.user)
			)
		for row in device_rows:
			op = row.operation
			res_id = row.resource_id
			if res_id not in bookings:
				continue
			t = getattr(op, 'op_type', None)
			primary = getattr(op, 'primary_surgeon', None)
			label = 'OP'
			if t is not None and getattr(t, 'name', None):
				label = str(t.name)
			if primary is not None:
				label = f"{label} – {doctor_display_name(primary)}"
			bookings[res_id].append(
				{
					'kind': 'operation',
					'id': op.id,
					'start_time': op.start_time,
					'end_time': op.end_time,
					'color': getattr(t, 'color', None) if t is not None else None,
					'label': label,
					'status': _booking_status_for_operation(op),
					'progress': OperationDashboardSerializer().get_progress(op),
				}
			)

		# 4) Doctor absence/break (added to every selected resource column)
		# Spec: absence=gelb, break=orange.
		ABSENCE_COLOR = '#FFD700'
		BREAK_COLOR = '#FFA500'

		abs_qs = DoctorAbsence.objects.using('default').filter(active=True, start_date__lte=day, end_date__gte=day)
		break_qs = DoctorBreak.objects.using('default').filter(active=True, date=day)
		if role_name == 'doctor':
			abs_qs = abs_qs.filter(doctor=request.user)
			break_qs = break_qs.filter(Q(doctor__isnull=True) | Q(doctor=request.user))

		absences = list(abs_qs.select_related('doctor').order_by('doctor_id', 'start_date', 'end_date', 'id'))
		breaks = list(break_qs.select_related('doctor').order_by('start_time', 'doctor_id', 'id'))

		for res_id in selected_ids:
			for a in absences:
				doc = getattr(a, 'doctor', None)
				reason = getattr(a, 'reason', None) or 'Abwesenheit'
				if doc is not None:
					reason = f"{reason} – {doctor_display_name(doc)}"
				bookings[res_id].append(
					{
						'kind': 'absence',
						'id': a.id,
						'start_time': range_start,
						'end_time': range_end,
						'color': ABSENCE_COLOR,
						'label': reason,
						'status': None,
					}
				)
			for b in breaks:
				doc = getattr(b, 'doctor', None)
				label = 'Pause'
				if doc is not None:
					label = f"{label} – {doctor_display_name(doc)}"
				start_dt = timezone.make_aware(datetime.combine(day, b.start_time), tz)
				end_dt = timezone.make_aware(datetime.combine(day, b.end_time), tz)
				bookings[res_id].append(
					{
						'kind': 'break',
						'id': b.id,
						'start_time': start_dt,
						'end_time': end_dt,
						'color': BREAK_COLOR,
						'label': label,
						'status': None,
					}
				)

		# Sort bookings by start_time
		payload = []
		for r in ordered_resources:
			items = bookings.get(r.id, [])
			items.sort(key=lambda x: (x.get('start_time'), x.get('end_time'), x.get('kind'), x.get('id')))
			payload.append({'resource': r, 'bookings': items})

		log_patient_action(request.user, 'resource_calendar_view', meta={'date': day.isoformat(), 'resource_ids': resource_ids})
		return Response(self.get_serializer(payload, many=True).data, status=status.HTTP_200_OK)


class PatientFlowListCreateView(generics.ListCreateAPIView):
	permission_classes = [PatientFlowPermission]
	queryset = PatientFlow.objects.using('default').all()

	def get_serializer_class(self):
		if self.request.method in ('POST', 'PUT', 'PATCH'):
			return PatientFlowCreateUpdateSerializer
		return PatientFlowSerializer

	def get_queryset(self):
		qs = (
			PatientFlow.objects.using('default')
			.select_related(
				'appointment',
				'appointment__type',
				'appointment__doctor',
				'operation',
				'operation__op_type',
				'operation__op_room',
				'operation__primary_surgeon',
				'operation__assistant',
				'operation__anesthesist',
			)
			.order_by('-status_changed_at', '-id')
		)
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			qs = qs.filter(
				Q(appointment__doctor=self.request.user)
				| Q(operation__primary_surgeon=self.request.user)
				| Q(operation__assistant=self.request.user)
				| Q(operation__anesthesist=self.request.user)
			)
		return qs

	def list(self, request, *args, **kwargs):
		r = super().list(request, *args, **kwargs)
		log_patient_action(request.user, 'patient_flow_view')
		return r

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		flow: PatientFlow = serializer.save()
		# Initial creation doesn't count as update/status-change audit by spec.
		out = PatientFlowSerializer(flow, context={'request': request}).data
		headers = self.get_success_headers(out)
		return Response(out, status=status.HTTP_201_CREATED, headers=headers)


class PatientFlowDetailView(generics.RetrieveUpdateDestroyAPIView):
	permission_classes = [PatientFlowPermission]
	queryset = PatientFlow.objects.using('default').all()

	def get_serializer_class(self):
		if self.request.method in ('PUT', 'PATCH'):
			return PatientFlowCreateUpdateSerializer
		return PatientFlowSerializer

	def get_queryset(self):
		# Apply the same RBAC filter as list.
		qs = (
			PatientFlow.objects.using('default')
			.select_related(
				'appointment',
				'appointment__type',
				'appointment__doctor',
				'operation',
				'operation__op_type',
				'operation__op_room',
				'operation__primary_surgeon',
				'operation__assistant',
				'operation__anesthesist',
			)
			.order_by('-status_changed_at', '-id')
		)
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			qs = qs.filter(
				Q(appointment__doctor=self.request.user)
				| Q(operation__primary_surgeon=self.request.user)
				| Q(operation__assistant=self.request.user)
				| Q(operation__anesthesist=self.request.user)
			)
		return qs

	def retrieve(self, request, *args, **kwargs):
		r = super().retrieve(request, *args, **kwargs)
		log_patient_action(request.user, 'patient_flow_view')
		return r

	def update(self, request, *args, **kwargs):
		obj = self.get_object()
		old_status = getattr(obj, 'status', None)
		r = super().update(request, *args, **kwargs)
		log_patient_action(request.user, 'patient_flow_update')
		# If status changed via general update, also log status-update audit.
		obj.refresh_from_db(using='default')
		new_status = getattr(obj, 'status', None)
		if new_status != old_status:
			patient_id = None
			appt = getattr(obj, 'appointment', None)
			op = getattr(obj, 'operation', None)
			if appt is not None:
				patient_id = getattr(appt, 'patient_id', None)
			elif op is not None:
				patient_id = getattr(op, 'patient_id', None)
			log_patient_action(
				request.user,
				'patient_flow_status_update',
				patient_id=patient_id,
				meta={'flow_id': obj.id, 'from': old_status, 'to': new_status},
			)
		return r

	def partial_update(self, request, *args, **kwargs):
		return self.update(request, *args, **kwargs)


class PatientFlowStatusUpdateView(generics.GenericAPIView):
	permission_classes = [PatientFlowPermission]
	serializer_class = PatientFlowStatusUpdateSerializer
	queryset = PatientFlow.objects.using('default').all()

	def get_queryset(self):
		# same RBAC filter as list
		qs = PatientFlow.objects.using('default').select_related(
			'appointment', 'appointment__doctor', 'operation', 'operation__primary_surgeon', 'operation__assistant', 'operation__anesthesist'
		)
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			qs = qs.filter(
				Q(appointment__doctor=self.request.user)
				| Q(operation__primary_surgeon=self.request.user)
				| Q(operation__assistant=self.request.user)
				| Q(operation__anesthesist=self.request.user)
			)
		return qs

	def patch(self, request, *args, **kwargs):
		obj = self.get_object()
		old_status = getattr(obj, 'status', None)
		ser = self.get_serializer(instance=obj, data=request.data, partial=True)
		ser.is_valid(raise_exception=True)
		obj = ser.save()

		patient_id = None
		appt = getattr(obj, 'appointment', None)
		op = getattr(obj, 'operation', None)
		if appt is not None:
			patient_id = getattr(appt, 'patient_id', None)
		elif op is not None:
			patient_id = getattr(op, 'patient_id', None)

		log_patient_action(
			request.user,
			'patient_flow_status_update',
			patient_id=patient_id,
			meta={'flow_id': obj.id, 'from': old_status, 'to': getattr(obj, 'status', None)},
		)
		return Response(PatientFlowSerializer(obj, context={'request': request}).data, status=status.HTTP_200_OK)


class PatientFlowLiveView(generics.ListAPIView):
	permission_classes = [PatientFlowPermission]
	serializer_class = PatientFlowSerializer

	def get_queryset(self):
		qs = (
			PatientFlow.objects.using('default')
			.exclude(status=PatientFlow.STATUS_DONE)
			.select_related(
				'appointment',
				'appointment__type',
				'appointment__doctor',
				'operation',
				'operation__op_type',
				'operation__op_room',
				'operation__primary_surgeon',
				'operation__assistant',
				'operation__anesthesist',
			)
			.order_by('-status_changed_at', '-id')
		)
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			qs = qs.filter(
				Q(appointment__doctor=self.request.user)
				| Q(operation__primary_surgeon=self.request.user)
				| Q(operation__assistant=self.request.user)
				| Q(operation__anesthesist=self.request.user)
			)
		return qs

	def list(self, request, *args, **kwargs):
		r = super().list(request, *args, **kwargs)
		log_patient_action(request.user, 'patient_flow_view', meta={'live': True})
		return r


class OpDashboardView(generics.GenericAPIView):
	permission_classes = [OpDashboardPermission]
	serializer_class = OperationDashboardSerializer

	def _parse_date(self, request):
		date_str = request.query_params.get('date')
		if not date_str:
			return None, Response(
				{'detail': 'date query parameter is required (YYYY-MM-DD).'},
				status=status.HTTP_400_BAD_REQUEST,
			)
		try:
			return datetime.strptime(date_str, '%Y-%m-%d').date(), None
		except ValueError:
			return None, Response(
				{'detail': 'date must be in format YYYY-MM-DD.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

	def _apply_rbac(self, request, qs):
		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			qs = qs.filter(
				Q(primary_surgeon=request.user)
				| Q(assistant=request.user)
				| Q(anesthesist=request.user)
			)
		return qs

	def get(self, request, *args, **kwargs):
		date_obj, err = self._parse_date(request)
		if err is not None:
			return err

		tz = timezone.get_current_timezone()
		range_start = timezone.make_aware(datetime.combine(date_obj, time.min), tz)
		range_end = timezone.make_aware(datetime.combine(date_obj, time.max), tz)
		range_end_for_query = range_end + timedelta(microseconds=1)

		qs = Operation.objects.using('default').filter(
			start_time__lt=range_end_for_query,
			end_time__gt=range_start,
		)
		qs = self._apply_rbac(request, qs)
		qs = qs.order_by('start_time', 'id')

		log_patient_action(request.user, 'op_dashboard_view', meta={'date': date_obj.isoformat()})
		data = self.get_serializer(qs, many=True, context={'request': request}).data
		return Response({'date': date_obj.isoformat(), 'operations': data}, status=status.HTTP_200_OK)


class OpDashboardLiveView(generics.GenericAPIView):
	permission_classes = [OpDashboardPermission]
	serializer_class = OperationDashboardSerializer

	def _apply_rbac(self, request, qs):
		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			qs = qs.filter(
				Q(primary_surgeon=request.user)
				| Q(assistant=request.user)
				| Q(anesthesist=request.user)
			)
		return qs

	def get(self, request, *args, **kwargs):
		now = timezone.now()
		qs = Operation.objects.using('default').filter(
			status=Operation.STATUS_RUNNING,
			start_time__lte=now,
		)
		qs = self._apply_rbac(request, qs).order_by('start_time', 'id')
		log_patient_action(request.user, 'op_dashboard_view', meta={'live': True})
		data = self.get_serializer(qs, many=True, context={'request': request}).data
		return Response({'operations': data}, status=status.HTTP_200_OK)


class OpDashboardStatusUpdateView(generics.GenericAPIView):
	permission_classes = [OpDashboardPermission]
	serializer_class = OperationDashboardSerializer

	def patch(self, request, pk: int, *args, **kwargs):
		obj = Operation.objects.using('default').filter(id=pk).first()
		if obj is None:
			return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

		def _audit(*, ok: bool, detail: str | None = None, meta: dict | None = None):
			payload = {'from': obj.status, 'to': (request.data or {}).get('status')}
			if meta:
				payload.update(meta)
			payload['ok'] = bool(ok)
			if detail:
				payload['detail'] = detail
			log_patient_action(
				request.user,
				'op_status_update',
				obj.patient_id,
				meta=payload,
			)

		new_status = (request.data or {}).get('status')
		if not new_status:
			_audit(ok=False, detail='status is required')
			return Response({'detail': 'status is required.'}, status=status.HTTP_400_BAD_REQUEST)

		old_status = obj.status
		allowed = False
		if new_status == Operation.STATUS_CANCELLED:
			allowed = True
		elif old_status == Operation.STATUS_PLANNED and new_status == Operation.STATUS_CONFIRMED:
			allowed = True
		elif old_status == Operation.STATUS_CONFIRMED and new_status == Operation.STATUS_RUNNING:
			allowed = True
		elif old_status == Operation.STATUS_RUNNING and new_status == Operation.STATUS_DONE:
			allowed = True

		if not allowed:
			_audit(ok=False, detail='invalid_transition', meta={'from': old_status, 'to': new_status})
			return Response(
				{'detail': 'Invalid status transition.', 'from': old_status, 'to': new_status},
				status=status.HTTP_400_BAD_REQUEST,
			)

		now = timezone.now()
		if new_status == Operation.STATUS_RUNNING and now < obj.start_time:
			_audit(ok=False, detail='running_before_start', meta={'from': old_status, 'to': new_status})
			return Response(
				{'detail': 'running is only allowed when now >= start_time.'},
				status=status.HTTP_400_BAD_REQUEST,
			)
		if new_status == Operation.STATUS_DONE and old_status != Operation.STATUS_RUNNING:
			_audit(ok=False, detail='done_not_running', meta={'from': old_status, 'to': new_status})
			return Response(
				{'detail': 'done is only allowed when previous status was running.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

		obj.status = new_status
		obj.save(update_fields=['status', 'updated_at'])
		_audit(ok=True, meta={'from': old_status, 'to': new_status})

		data = self.get_serializer(obj, context={'request': request}).data
		return Response(data, status=status.HTTP_200_OK)


class AppointmentListCreateView(generics.ListCreateAPIView):
	"""
	List and create appointments.
	
	POST uses the scheduling service for full validation including:
	- Working hours validation
	- Doctor absence validation
	- Break validation
	- Conflict detection (doctor, room, device, patient)
	"""
	permission_classes = [AppointmentPermission]
	use_scheduling_service = True  # Set to False to use legacy serializer-based validation

	def get_queryset(self):
		qs = Appointment.objects.using('default').all()

		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			return qs.filter(doctor=self.request.user)

		return qs

	def get_serializer_class(self):
		if self.request.method == 'POST':
			return AppointmentCreateUpdateSerializer
		return AppointmentSerializer

	def list(self, request, *args, **kwargs):
		log_patient_action(request.user, 'appointment_list')
		return super().list(request, *args, **kwargs)

	def create(self, request, *args, **kwargs):
		"""
		Create an appointment using the scheduling service.
		
		The scheduling service performs full validation and conflict detection.
		Scheduling exceptions are translated to appropriate HTTP responses.
		"""
		if self.use_scheduling_service:
			return self._create_with_scheduling_service(request)
		return self._create_legacy(request)

	def _create_legacy(self, request):
		"""Legacy create using serializer validation only."""
		write_serializer = self.get_serializer(data=request.data)
		write_serializer.is_valid(raise_exception=True)
		appointment = write_serializer.save()
		log_patient_action(request.user, 'appointment_create', appointment.patient_id)

		read_serializer = AppointmentSerializer(appointment, context={'request': request})
		headers = self.get_success_headers(read_serializer.data)
		return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

	def _create_with_scheduling_service(self, request):
		"""Create using the scheduling service with full validation."""
		# First validate basic field structure with serializer
		write_serializer = self.get_serializer(data=request.data)
		write_serializer.is_valid(raise_exception=True)
		validated_data = write_serializer.validated_data

		# Extract doctor_id from validated doctor object
		doctor = validated_data.get('doctor')
		doctor_id = doctor.id if doctor else None

		# Build data dict for scheduling service
		scheduling_data = {
			'patient_id': validated_data.get('patient_id'),
			'doctor_id': doctor_id,
			'start_time': validated_data.get('start_time'),
			'end_time': validated_data.get('end_time'),
			'type_id': validated_data.get('type').id if validated_data.get('type') else None,
			'resource_ids': validated_data.get('resource_ids'),
			'status': validated_data.get('status', Appointment.STATUS_SCHEDULED),
			'notes': validated_data.get('notes', ''),
		}

		try:
			appointment = scheduling_plan_appointment(
				data=scheduling_data,
				user=request.user,
			)
		except SchedulingConflictError as e:
			return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
		except WorkingHoursViolation as e:
			return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
		except DoctorAbsentError as e:
			return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
		except DoctorBreakConflict as e:
			return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
		except InvalidSchedulingData as e:
			return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
		except SchedulingError as e:
			return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

		read_serializer = AppointmentSerializer(appointment, context={'request': request})
		headers = self.get_success_headers(read_serializer.data)
		return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AppointmentDetailView(generics.RetrieveUpdateDestroyAPIView):
	permission_classes = [AppointmentPermission]
	queryset = Appointment.objects.using('default').all()

	def get_serializer_class(self):
		if self.request.method in ('PUT', 'PATCH'):
			return AppointmentCreateUpdateSerializer
		return AppointmentSerializer

	def retrieve(self, request, *args, **kwargs):
		appointment = self.get_object()
		log_patient_action(request.user, 'appointment_view', appointment.patient_id)
		return super().retrieve(request, *args, **kwargs)

	def update(self, request, *args, **kwargs):
		partial = kwargs.pop('partial', False)
		appointment = self.get_object()

		write_serializer = AppointmentCreateUpdateSerializer(
			appointment,
			data=request.data,
			partial=partial,
			context={'request': request},
		)
		write_serializer.is_valid(raise_exception=True)
		updated = write_serializer.save()

		log_patient_action(request.user, 'appointment_update', updated.patient_id)
		read_serializer = AppointmentSerializer(updated, context={'request': request})
		return Response(read_serializer.data, status=status.HTTP_200_OK)

	def destroy(self, request, *args, **kwargs):
		appointment = self.get_object()
		patient_id = appointment.patient_id
		response = super().destroy(request, *args, **kwargs)
		log_patient_action(request.user, 'appointment_delete', patient_id)
		return response


class AppointmentSuggestView(generics.GenericAPIView):
	permission_classes = [AppointmentSuggestPermission]

	def _parse_iso_dt(self, value: str) -> datetime:
		# Accept 'Z' and offsets.
		if value.endswith('Z'):
			value = value[:-1] + '+00:00'
			return datetime.fromisoformat(value)
		return datetime.fromisoformat(value)

	def _parse_int(self, request, key: str, *, required: bool = False, default=None):
		value = request.query_params.get(key)
		if value in (None, ''):
			if required:
				return None, Response(
					{'detail': f'{key} query parameter is required.'},
					status=status.HTTP_400_BAD_REQUEST,
				)
			return default, None
		try:
			return int(value), None
		except ValueError:
			return None, Response(
				{'detail': f'{key} must be an integer.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

	def _parse_date(self, request, key: str, *, default_value: date):
		value = request.query_params.get(key)
		if value in (None, ''):
			return default_value, None
		try:
			return datetime.strptime(value, '%Y-%m-%d').date(), None
		except ValueError:
			return None, Response(
				{'detail': f'{key} must be in format YYYY-MM-DD.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

	def _parse_int_list(self, request, key: str):
		"""Parse comma-separated list of ints.

		Examples:
		- ?resource_ids=1,2,3
		- ?resource_ids=
		"""
		value = request.query_params.get(key)
		if value in (None, ''):
			return None, None
		parts = [p.strip() for p in str(value).split(',') if p.strip()]
		ids = []
		try:
			for p in parts:
				ids.append(int(p))
		except ValueError:
			return None, Response(
				{'detail': f'{key} must be a comma-separated list of integers.'},
				status=status.HTTP_400_BAD_REQUEST,
			)
		# de-dup preserve order
		seen = set()
		unique = []
		for i in ids:
			if i not in seen:
				seen.add(i)
				unique.append(i)
		return unique, None

	def get(self, request, *args, **kwargs):
		doctor_id, err = self._parse_int(request, 'doctor_id', required=True)
		if err is not None:
			return err

		type_id, err = self._parse_int(request, 'type_id')
		if err is not None:
			return err

		duration_minutes, err = self._parse_int(request, 'duration_minutes')
		if err is not None:
			return err

		start_date, err = self._parse_date(request, 'start_date', default_value=timezone.localdate())
		if err is not None:
			return err

		limit, err = self._parse_int(request, 'limit', default=1)
		if err is not None:
			return err
		if limit is None or limit <= 0:
			return Response({'detail': 'limit must be >= 1.'}, status=status.HTTP_400_BAD_REQUEST)

		# Resolve doctor
		doctor = resolve_doctor(doctor_id)
		if doctor is None:
			return Response({'detail': 'doctor_id not found.'}, status=status.HTTP_400_BAD_REQUEST)
		role_name = getattr(getattr(doctor, 'role', None), 'name', None)
		if role_name != 'doctor':
			return Response({'detail': 'doctor_id must reference a user with role "doctor".'}, status=status.HTTP_400_BAD_REQUEST)
		if not getattr(doctor, 'is_active', True):
			return Response({'detail': 'doctor_id must reference an active doctor.'}, status=status.HTTP_400_BAD_REQUEST)

		# Resolve type + duration
		type_obj = None
		if type_id is not None:
			type_obj = AppointmentType.objects.using('default').filter(id=type_id).first()
			if type_obj is None:
				return Response({'detail': 'type_id not found.'}, status=status.HTTP_400_BAD_REQUEST)
			if not getattr(type_obj, 'active', True):
				return Response({'detail': 'type_id is inactive.'}, status=status.HTTP_400_BAD_REQUEST)

		if duration_minutes is None:
			if type_obj is None:
				return Response(
					{'detail': 'duration_minutes is required when type_id is not provided.'},
					status=status.HTTP_400_BAD_REQUEST,
				)
			duration_minutes = getattr(type_obj, 'duration_minutes', None)
			if not duration_minutes:
				return Response(
					{'detail': 'AppointmentType.duration_minutes is not set; provide duration_minutes.'},
					status=status.HTTP_400_BAD_REQUEST,
				)

		if duration_minutes <= 0:
			return Response({'detail': 'duration_minutes must be >= 1.'}, status=status.HTTP_400_BAD_REQUEST)

		resource_ids, err = self._parse_int_list(request, 'resource_ids')
		if err is not None:
			return err

		resources = None
		if resource_ids is not None:
			resources = list(
				Resource.objects.using('default')
				.filter(id__in=resource_ids, active=True)
				.order_by('id')
			)
			found = {r.id for r in resources}
			missing = [rid for rid in resource_ids if rid not in found]
			if missing:
				return Response(
					{'detail': 'resource_ids contains unknown or inactive resource(s).'},
					status=status.HTTP_400_BAD_REQUEST,
				)

		primary_suggestions = compute_suggestions_for_doctor(
			doctor=doctor,
			start_date=start_date,
			end_date=start_date,
			duration_minutes=duration_minutes,
			limit=limit,
			type_obj=type_obj,
			resources=resources,
			max_days=1,
		)

		fallback_suggestions = []
		used_fallback = False
		if not primary_suggestions:
			used_fallback = True
			reps = get_active_doctors(exclude_doctor_id=doctor.id)
			items = []
			for rep in reps:
				rep_suggestions = compute_suggestions_for_doctor(
					doctor=rep,
					start_date=start_date,
						end_date=start_date,
					duration_minutes=duration_minutes,
					limit=limit,
					type_obj=type_obj,
					resources=resources,
						max_days=1,
				)
				if rep_suggestions:
					items.append(
						{
							'doctor': {
								'id': rep.id,
								'name': doctor_display_name(rep),
								'color': getattr(rep, 'calendar_color', None),
							},
							'suggestions': rep_suggestions,
							'_sort': self._parse_iso_dt(rep_suggestions[0]['start_time']),
						}
					)

			items.sort(key=lambda x: x['_sort'])
			for item in items:
				item.pop('_sort', None)
			fallback_suggestions = items

		log_patient_action(request.user, 'appointment_suggest')
		if used_fallback and fallback_suggestions:
			log_patient_action(request.user, 'doctor_substitution_suggest')
		return Response(
			{
				'primary_doctor': {
					'id': doctor.id,
					'name': doctor_display_name(doctor),
					'color': getattr(doctor, 'calendar_color', None),
				},
				'primary_suggestions': primary_suggestions,
				'fallback_suggestions': fallback_suggestions,
			},
			status=status.HTTP_200_OK,
		)


class AppointmentTypeListCreateView(generics.ListCreateAPIView):
	permission_classes = [AppointmentTypePermission]
	queryset = AppointmentType.objects.all()
	serializer_class = AppointmentTypeSerializer

	def list(self, request, *args, **kwargs):
		log_patient_action(request.user, 'appointment_type_list')
		return super().list(request, *args, **kwargs)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		obj = serializer.save()
		log_patient_action(request.user, 'appointment_type_create')
		headers = self.get_success_headers(serializer.data)
		return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AppointmentTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
	permission_classes = [AppointmentTypePermission]
	queryset = AppointmentType.objects.all()
	serializer_class = AppointmentTypeSerializer

	def retrieve(self, request, *args, **kwargs):
		log_patient_action(request.user, 'appointment_type_view')
		return super().retrieve(request, *args, **kwargs)

	def update(self, request, *args, **kwargs):
		response = super().update(request, *args, **kwargs)
		log_patient_action(request.user, 'appointment_type_update')
		return response


class OperationTypeListCreateView(generics.ListCreateAPIView):
	permission_classes = [OperationTypePermission]
	queryset = OperationType.objects.using('default').all()
	serializer_class = OperationTypeSerializer

	def get_queryset(self):
		return OperationType.objects.using('default').all().order_by('name', 'id')

	def list(self, request, *args, **kwargs):
		log_patient_action(request.user, 'operation_type_list')
		return super().list(request, *args, **kwargs)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		log_patient_action(request.user, 'operation_type_create')
		headers = self.get_success_headers(serializer.data)
		return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class OperationTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
	permission_classes = [OperationTypePermission]
	queryset = OperationType.objects.using('default').all()
	serializer_class = OperationTypeSerializer

	def retrieve(self, request, *args, **kwargs):
		log_patient_action(request.user, 'operation_type_view')
		return super().retrieve(request, *args, **kwargs)

	def update(self, request, *args, **kwargs):
		r = super().update(request, *args, **kwargs)
		log_patient_action(request.user, 'operation_type_update')
		return r

	def destroy(self, request, *args, **kwargs):
		r = super().destroy(request, *args, **kwargs)
		log_patient_action(request.user, 'operation_type_delete')
		return r


class OperationListCreateView(generics.ListCreateAPIView):
	"""
	List and create operations.
	
	POST uses the scheduling service for full validation including:
	- Doctor absence validation (for all team members)
	- Conflict detection (room, devices, all team members, patient)
	"""
	permission_classes = [OperationPermission]
	use_scheduling_service = True  # Set to False to use legacy serializer-based validation

	def get_queryset(self):
		qs = Operation.objects.using('default').all()
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			qs = qs.filter(
				Q(primary_surgeon=self.request.user)
				| Q(assistant=self.request.user)
				| Q(anesthesist=self.request.user)
			)
		return qs.order_by('start_time', 'id')

	def get_serializer_class(self):
		if self.request.method == 'POST':
			return OperationCreateUpdateSerializer
		return OperationSerializer

	def list(self, request, *args, **kwargs):
		log_patient_action(request.user, 'operation_list')
		return super().list(request, *args, **kwargs)

	def create(self, request, *args, **kwargs):
		"""
		Create an operation using the scheduling service.
		
		The scheduling service performs full validation and conflict detection.
		Scheduling exceptions are translated to appropriate HTTP responses.
		"""
		if self.use_scheduling_service:
			return self._create_with_scheduling_service(request)
		return self._create_legacy(request)

	def _create_legacy(self, request):
		"""Legacy create using serializer validation only."""
		write_serializer = self.get_serializer(data=request.data, context={'request': request})
		write_serializer.is_valid(raise_exception=True)
		obj = write_serializer.save()
		log_patient_action(request.user, 'operation_create', obj.patient_id)

		read_serializer = OperationSerializer(obj, context={'request': request})
		headers = self.get_success_headers(read_serializer.data)
		return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

	def _create_with_scheduling_service(self, request):
		"""Create using the scheduling service with full validation."""
		# First validate basic field structure with serializer
		write_serializer = self.get_serializer(data=request.data, context={'request': request})
		write_serializer.is_valid(raise_exception=True)
		validated_data = write_serializer.validated_data

		# Extract IDs from validated objects
		primary_surgeon = validated_data.get('primary_surgeon')
		assistant = validated_data.get('assistant')
		anesthesist = validated_data.get('anesthesist')
		op_room = validated_data.get('op_room')
		op_type = validated_data.get('op_type')

		# Build data dict for scheduling service
		scheduling_data = {
			'patient_id': validated_data.get('patient_id'),
			'primary_surgeon_id': primary_surgeon.id if primary_surgeon else None,
			'assistant_id': assistant.id if assistant else None,
			'anesthesist_id': anesthesist.id if anesthesist else None,
			'op_room_id': op_room.id if op_room else None,
			'op_type_id': op_type.id if op_type else None,
			'start_time': validated_data.get('start_time'),
			'op_device_ids': validated_data.get('op_device_ids', []),
			'status': validated_data.get('status', Operation.STATUS_PLANNED),
			'notes': validated_data.get('notes', ''),
		}

		try:
			operation = scheduling_plan_operation(
				data=scheduling_data,
				user=request.user,
			)
		except SchedulingConflictError as e:
			return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
		except WorkingHoursViolation as e:
			return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
		except DoctorAbsentError as e:
			return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
		except DoctorBreakConflict as e:
			return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
		except InvalidSchedulingData as e:
			return Response(e.to_dict(), status=status.HTTP_400_BAD_REQUEST)
		except SchedulingError as e:
			return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

		read_serializer = OperationSerializer(operation, context={'request': request})
		headers = self.get_success_headers(read_serializer.data)
		return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class OperationDetailView(generics.RetrieveUpdateDestroyAPIView):
	permission_classes = [OperationPermission]
	queryset = Operation.objects.using('default').all()

	def get_serializer_class(self):
		if self.request.method in ('PUT', 'PATCH'):
			return OperationCreateUpdateSerializer
		return OperationSerializer

	def retrieve(self, request, *args, **kwargs):
		obj = self.get_object()
		log_patient_action(request.user, 'operation_view', obj.patient_id)
		return super().retrieve(request, *args, **kwargs)

	def update(self, request, *args, **kwargs):
		partial = kwargs.pop('partial', False)
		obj = self.get_object()
		write_serializer = OperationCreateUpdateSerializer(
			obj,
			data=request.data,
			partial=partial,
			context={'request': request},
		)
		write_serializer.is_valid(raise_exception=True)
		updated = write_serializer.save()
		log_patient_action(request.user, 'operation_update', updated.patient_id)
		read_serializer = OperationSerializer(updated, context={'request': request})
		return Response(read_serializer.data, status=status.HTTP_200_OK)

	def destroy(self, request, *args, **kwargs):
		obj = self.get_object()
		patient_id = obj.patient_id
		r = super().destroy(request, *args, **kwargs)
		log_patient_action(request.user, 'operation_delete', patient_id)
		return r


class OperationSuggestView(generics.GenericAPIView):
	permission_classes = [OperationSuggestPermission]

	def _parse_int(self, request, key: str, *, required: bool = False, default=None):
		value = request.query_params.get(key)
		if value in (None, ''):
			if required:
				return None, Response(
					{'detail': f'{key} query parameter is required.'},
					status=status.HTTP_400_BAD_REQUEST,
				)
			return default, None
		try:
			return int(value), None
		except ValueError:
			return None, Response(
				{'detail': f'{key} must be an integer.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

	def _parse_date(self, request, key: str, *, default_value: date):
		value = request.query_params.get(key)
		if value in (None, ''):
			return default_value, None
		try:
			return datetime.strptime(value, '%Y-%m-%d').date(), None
		except ValueError:
			return None, Response(
				{'detail': f'{key} must be in format YYYY-MM-DD.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

	def _parse_int_list(self, request, key: str):
		value = request.query_params.get(key)
		if value in (None, ''):
			return None, None
		parts = [p.strip() for p in str(value).split(',') if p.strip()]
		ids = []
		try:
			for p in parts:
				ids.append(int(p))
		except ValueError:
			return None, Response(
				{'detail': f'{key} must be a comma-separated list of integers.'},
				status=status.HTTP_400_BAD_REQUEST,
			)
		seen = set()
		unique = []
		for i in ids:
			if i not in seen:
				seen.add(i)
				unique.append(i)
		return unique, None

	def get(self, request, *args, **kwargs):
		patient_id, err = self._parse_int(request, 'patient_id', required=True)
		if err is not None:
			return err

		primary_surgeon_id, err = self._parse_int(request, 'primary_surgeon_id', required=True)
		if err is not None:
			return err

		assistant_id, err = self._parse_int(request, 'assistant_id')
		if err is not None:
			return err

		anesthesist_id, err = self._parse_int(request, 'anesthesist_id')
		if err is not None:
			return err

		op_type_id, err = self._parse_int(request, 'op_type_id', required=True)
		if err is not None:
			return err

		op_room_id, err = self._parse_int(request, 'op_room_id', required=True)
		if err is not None:
			return err

		op_device_ids, err = self._parse_int_list(request, 'op_device_ids')
		if err is not None:
			return err

		start_date, err = self._parse_date(request, 'start_date', default_value=timezone.localdate())
		if err is not None:
			return err

		limit, err = self._parse_int(request, 'limit', default=3)
		if err is not None:
			return err
		if limit is None or limit <= 0:
			return Response({'detail': 'limit must be >= 1.'}, status=status.HTTP_400_BAD_REQUEST)

		# Validate core references (serializer also validates, but we want clean 400s)
		primary_surgeon = resolve_doctor(primary_surgeon_id)
		if primary_surgeon is None:
			return Response({'detail': 'primary_surgeon_id not found.'}, status=status.HTTP_400_BAD_REQUEST)
		if getattr(getattr(primary_surgeon, 'role', None), 'name', None) != 'doctor':
			return Response({'detail': 'primary_surgeon_id must reference a user with role "doctor".'}, status=status.HTTP_400_BAD_REQUEST)
		if not getattr(primary_surgeon, 'is_active', True):
			return Response({'detail': 'primary_surgeon_id must reference an active doctor.'}, status=status.HTTP_400_BAD_REQUEST)

		op_type = OperationType.objects.using('default').filter(id=op_type_id).first()
		if op_type is None:
			return Response({'detail': 'op_type_id not found.'}, status=status.HTTP_400_BAD_REQUEST)
		if not getattr(op_type, 'active', True):
			return Response({'detail': 'op_type_id is inactive.'}, status=status.HTTP_400_BAD_REQUEST)

		op_room = Resource.objects.using('default').filter(id=op_room_id, active=True).first()
		if op_room is None:
			return Response({'detail': 'op_room_id not found.'}, status=status.HTTP_400_BAD_REQUEST)
		if getattr(op_room, 'type', None) != 'room':
			return Response({'detail': 'op_room_id must reference a Resource with type "room".'}, status=status.HTTP_400_BAD_REQUEST)

		# Scan: propose the earliest valid slot per day window
		weekday = start_date.weekday()
		practice_hours = list(
			PracticeHours.objects.using('default').filter(weekday=weekday, active=True).order_by('start_time', 'id')
		)
		doctor_hours = list(
			DoctorHours.objects.using('default').filter(doctor=primary_surgeon, weekday=weekday, active=True).order_by('start_time', 'id')
		)
		if not (practice_hours and doctor_hours):
			log_patient_action(request.user, 'operation_suggest')
			return Response(
				{
					'primary_surgeon': {
						'id': primary_surgeon.id,
						'name': doctor_display_name(primary_surgeon),
						'color': getattr(primary_surgeon, 'calendar_color', None),
					},
					'suggestions': [],
				},
				status=status.HTTP_200_OK,
			)

		tz = timezone.get_current_timezone()
		day_start = timezone.make_aware(datetime.combine(start_date, time.min), tz)
		now_local = timezone.localtime(timezone.now())

		step = timedelta(minutes=5)
		suggestions = []
		for ph in practice_hours:
			for dh in doctor_hours:
				window_start_t = max(ph.start_time, dh.start_time)
				window_end_t = min(ph.end_time, dh.end_time)
				if window_start_t >= window_end_t:
					continue
				window_start_dt = timezone.make_aware(datetime.combine(start_date, window_start_t), tz)
				window_end_dt = timezone.make_aware(datetime.combine(start_date, window_end_t), tz)

				candidate = window_start_dt
				if start_date == now_local.date():
					candidate = max(candidate, now_local)
				candidate = candidate.replace(second=0, microsecond=0)
				# align to 5 min
				mod = candidate.minute % 5
				if mod:
					candidate = candidate + timedelta(minutes=(5 - mod))

				while candidate < window_end_dt and len(suggestions) < limit:
					payload = {
						'patient_id': patient_id,
						'primary_surgeon': primary_surgeon_id,
						'assistant': assistant_id,
						'anesthesist': anesthesist_id,
						'op_room': op_room_id,
						'op_device_ids': op_device_ids or [],
						'op_type': op_type_id,
						'start_time': _iso_z(candidate),
						'status': 'planned',
						'notes': '',
					}
					ser = OperationCreateUpdateSerializer(
						data=payload,
						context={'request': request, 'suppress_conflict_audit': True},
					)
					if ser.is_valid():
						end_dt = ser.validated_data['end_time']
						suggestions.append(
							{
								'start_time': _iso_z(candidate),
								'end_time': _iso_z(end_dt),
								'op_type': {'id': op_type.id, 'name': op_type.name, 'color': op_type.color},
								'op_room': {'id': op_room.id, 'name': op_room.name, 'color': op_room.color},
								'op_device_ids': op_device_ids or [],
							}
						)
						break
					candidate = candidate + step

				if len(suggestions) >= limit:
					break
			if len(suggestions) >= limit:
				break

		log_patient_action(request.user, 'operation_suggest')
		return Response(
			{
				'primary_surgeon': {
					'id': primary_surgeon.id,
					'name': doctor_display_name(primary_surgeon),
					'color': getattr(primary_surgeon, 'calendar_color', None),
				},
				'suggestions': suggestions,
			},
			status=status.HTTP_200_OK,
		)

	def destroy(self, request, *args, **kwargs):
		response = super().destroy(request, *args, **kwargs)
		log_patient_action(request.user, 'appointment_type_delete')
		return response


def _iso_z(dt: datetime) -> str:
	# Consistent ISO output; prefer Z when in UTC.
	value = dt.isoformat()
	return value.replace('+00:00', 'Z')


class _CalendarBaseView(generics.GenericAPIView):
	permission_classes = [AppointmentPermission]
	serializer_class = AppointmentSerializer

	audit_action: str = ''

	def _parse_date(self, request):
		date_str = request.query_params.get('date')
		if not date_str:
			return None, Response(
				{'detail': 'date query parameter is required (YYYY-MM-DD).'},
				status=status.HTTP_400_BAD_REQUEST,
			)
		try:
			return datetime.strptime(date_str, '%Y-%m-%d').date(), None
		except ValueError:
			return None, Response(
				{'detail': 'date must be in format YYYY-MM-DD.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

	def _parse_int(self, request, key: str):
		value = request.query_params.get(key)
		if value in (None, ''):
			return None, None
		try:
			return int(value), None
		except ValueError:
			return None, Response(
				{'detail': f'{key} must be an integer.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

	def _apply_rbac(self, request, qs):
		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			return qs.filter(doctor=request.user)
		return qs

	def _apply_filters(self, request, qs):
		doctor_id, err = self._parse_int(request, 'doctor_id')
		if err is not None:
			return None, err
		patient_id, err = self._parse_int(request, 'patient_id')
		if err is not None:
			return None, err
		type_id, err = self._parse_int(request, 'type_id')
		if err is not None:
			return None, err

		if doctor_id is not None:
			qs = qs.filter(doctor_id=doctor_id)
		if patient_id is not None:
			qs = qs.filter(patient_id=patient_id)
		if type_id is not None:
			qs = qs.filter(type_id=type_id)

		return qs, None

	def _response(self, request, range_start: datetime, range_end_inclusive: datetime):
		doctor_id, err = self._parse_int(request, 'doctor_id')
		if err is not None:
			return err

		# Use __lt for end; make it effectively inclusive via +1 microsecond.
		range_end_for_query = range_end_inclusive + timedelta(microseconds=1)
		qs = Appointment.objects.filter(
			start_time__lt=range_end_for_query,
			end_time__gt=range_start,
		)
		qs = self._apply_rbac(request, qs)
		qs, err = self._apply_filters(request, qs)
		if err is not None:
			return err

		# Doctor absences for the same calendar range
		local_start = timezone.localtime(range_start) if timezone.is_aware(range_start) else range_start
		local_end = timezone.localtime(range_end_inclusive) if timezone.is_aware(range_end_inclusive) else range_end_inclusive
		range_start_date = local_start.date()
		range_end_date = local_end.date()

		abs_qs = DoctorAbsence.objects.using('default').filter(
			active=True,
			start_date__lte=range_end_date,
			end_date__gte=range_start_date,
		)

		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			abs_qs = abs_qs.filter(doctor=request.user)
		elif doctor_id is not None:
			abs_qs = abs_qs.filter(doctor_id=doctor_id)

		absences = DoctorAbsenceSerializer(abs_qs.order_by('doctor_id', 'start_date', 'end_date', 'id'), many=True).data

		break_qs = DoctorBreak.objects.using('default').filter(
			active=True,
			date__gte=range_start_date,
			date__lte=range_end_date,
		)

		if role_name == 'doctor':
			break_qs = break_qs.filter(Q(doctor__isnull=True) | Q(doctor=request.user))
		elif doctor_id is not None:
			break_qs = break_qs.filter(Q(doctor__isnull=True) | Q(doctor_id=doctor_id))

		breaks = DoctorBreakSerializer(break_qs.order_by('date', 'start_time', 'doctor_id', 'id'), many=True).data

		resources = ResourceSerializer(
			Resource.objects.using('default').filter(active=True).order_by('type', 'name', 'id'),
			many=True,
		).data

		# Resource bookings for appointments in this calendar response (respect RBAC+filters)
		resource_bookings = []
		appt_ids_qs = qs.values_list('id', flat=True)
		res_qs = (
			AppointmentResource.objects.using('default')
			.filter(appointment_id__in=appt_ids_qs)
			.select_related('appointment')
			.order_by('appointment__start_time', 'appointment_id', 'resource_id', 'id')
		)
		for ar in res_qs:
			appt = ar.appointment
			resource_bookings.append(
				{
					'appointment_id': ar.appointment_id,
					'resource_id': ar.resource_id,
					'start_time': _iso_z(appt.start_time),
					'end_time': _iso_z(appt.end_time),
				}
			)

		# Available doctors summary for UI.
		available_doctors = []
		doctors = []
		if role_name == 'doctor':
			doctors = [request.user]
		elif doctor_id is not None:
			maybe = resolve_doctor(doctor_id)
			if maybe is not None and getattr(getattr(maybe, 'role', None), 'name', None) == 'doctor' and getattr(maybe, 'is_active', True):
				doctors = [maybe]
		else:
			doctors = get_active_doctors()

		for d in doctors:
			av = availability_for_range(
				doctor=d,
				start_date=range_start_date,
				end_date=range_end_date,
				duration_minutes=30,
			)
			available_doctors.append(
				{
					'id': d.id,
					'name': doctor_display_name(d),
						'color': getattr(d, 'calendar_color', None),
					'available': bool(av.available),
					'reason': av.reason,
				}
			)

		log_patient_action(request.user, self.audit_action)
		log_patient_action(request.user, 'doctor_substitution_list')

		data = self.get_serializer(qs.order_by('start_time', 'id'), many=True).data

		# Operations in the same calendar range
		op_qs = Operation.objects.using('default').filter(
			start_time__lt=range_end_for_query,
			end_time__gt=range_start,
		)
		role_name = getattr(getattr(request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			op_qs = op_qs.filter(
				Q(primary_surgeon=request.user)
				| Q(assistant=request.user)
				| Q(anesthesist=request.user)
			)
		elif doctor_id is not None:
			op_qs = op_qs.filter(
				Q(primary_surgeon_id=doctor_id)
				| Q(assistant_id=doctor_id)
				| Q(anesthesist_id=doctor_id)
			)

		patient_id, err2 = self._parse_int(request, 'patient_id')
		if err2 is not None:
			return err2
		if patient_id is not None:
			op_qs = op_qs.filter(patient_id=patient_id)

		operations = OperationSerializer(op_qs.order_by('start_time', 'id'), many=True, context={'request': request}).data
		return Response(
			{
				'range_start': _iso_z(range_start),
				'range_end': _iso_z(range_end_inclusive),
				'appointments': data,
				'operations': operations,
				'absences': absences,
				'breaks': breaks,
				'resources': resources,
				'resource_bookings': resource_bookings,
				'available_doctors': available_doctors,
			},
			status=status.HTTP_200_OK,
		)


class ResourceListCreateView(generics.ListCreateAPIView):
	permission_classes = [ResourcePermission]
	queryset = Resource.objects.using('default').all()
	serializer_class = ResourceSerializer

	def get_queryset(self):
		return Resource.objects.using('default').all().order_by('type', 'name', 'id')

	def list(self, request, *args, **kwargs):
		log_patient_action(request.user, 'resource_list')
		return super().list(request, *args, **kwargs)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		log_patient_action(request.user, 'resource_create')
		headers = self.get_success_headers(serializer.data)
		return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class ResourceDetailView(generics.RetrieveUpdateDestroyAPIView):
	permission_classes = [ResourcePermission]
	queryset = Resource.objects.using('default').all()
	serializer_class = ResourceSerializer

	def update(self, request, *args, **kwargs):
		r = super().update(request, *args, **kwargs)
		log_patient_action(request.user, 'resource_update')
		return r

	def destroy(self, request, *args, **kwargs):
		r = super().destroy(request, *args, **kwargs)
		log_patient_action(request.user, 'resource_delete')
		return r


class CalendarDayView(_CalendarBaseView):
	audit_action = 'calendar_day'

	def get(self, request, *args, **kwargs):
		date_obj, err = self._parse_date(request)
		if err is not None:
			return err

		tz = timezone.get_current_timezone()
		range_start = timezone.make_aware(datetime.combine(date_obj, time.min), tz)
		range_end = timezone.make_aware(datetime.combine(date_obj, time.max), tz)
		return self._response(request, range_start, range_end)


class CalendarWeekView(_CalendarBaseView):
	audit_action = 'calendar_week'

	def get(self, request, *args, **kwargs):
		date_obj, err = self._parse_date(request)
		if err is not None:
			return err

		monday = date_obj - timedelta(days=date_obj.weekday())
		sunday = monday + timedelta(days=6)

		tz = timezone.get_current_timezone()
		range_start = timezone.make_aware(datetime.combine(monday, time.min), tz)
		range_end = timezone.make_aware(datetime.combine(sunday, time.max), tz)
		return self._response(request, range_start, range_end)


class CalendarMonthView(_CalendarBaseView):
	audit_action = 'calendar_month'

	def get(self, request, *args, **kwargs):
		date_obj, err = self._parse_date(request)
		if err is not None:
			return err

		year = date_obj.year
		month = date_obj.month
		first_day = date_obj.replace(day=1)
		last_day = date_obj.replace(day=calendar.monthrange(year, month)[1])

		tz = timezone.get_current_timezone()
		range_start = timezone.make_aware(datetime.combine(first_day, time.min), tz)
		range_end = timezone.make_aware(datetime.combine(last_day, time.max), tz)
		return self._response(request, range_start, range_end)


class PracticeHoursListCreateView(generics.ListCreateAPIView):
	permission_classes = [PracticeHoursPermission]
	queryset = PracticeHours.objects.using('default').all()
	serializer_class = PracticeHoursSerializer

	def list(self, request, *args, **kwargs):
		log_patient_action(request.user, 'practice_hours_list')
		return super().list(request, *args, **kwargs)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		log_patient_action(request.user, 'practice_hours_create')
		headers = self.get_success_headers(serializer.data)
		return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class PracticeHoursDetailView(generics.RetrieveUpdateDestroyAPIView):
	permission_classes = [PracticeHoursPermission]
	queryset = PracticeHours.objects.using('default').all()
	serializer_class = PracticeHoursSerializer

	def retrieve(self, request, *args, **kwargs):
		log_patient_action(request.user, 'practice_hours_view')
		return super().retrieve(request, *args, **kwargs)

	def update(self, request, *args, **kwargs):
		response = super().update(request, *args, **kwargs)
		log_patient_action(request.user, 'practice_hours_update')
		return response

	def destroy(self, request, *args, **kwargs):
		response = super().destroy(request, *args, **kwargs)
		log_patient_action(request.user, 'practice_hours_delete')
		return response


class DoctorHoursListCreateView(generics.ListCreateAPIView):
	permission_classes = [DoctorHoursPermission]
	serializer_class = DoctorHoursSerializer

	def get_queryset(self):
		qs = DoctorHours.objects.using('default').all()
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			return qs.filter(doctor=self.request.user)
		return qs

	def list(self, request, *args, **kwargs):
		log_patient_action(request.user, 'doctor_hours_list')
		return super().list(request, *args, **kwargs)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		log_patient_action(request.user, 'doctor_hours_create')
		headers = self.get_success_headers(serializer.data)
		return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class DoctorHoursDetailView(generics.RetrieveUpdateDestroyAPIView):
	permission_classes = [DoctorHoursPermission]
	serializer_class = DoctorHoursSerializer

	def get_queryset(self):
		qs = DoctorHours.objects.using('default').all()
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			return qs.filter(doctor=self.request.user)
		return qs

	def retrieve(self, request, *args, **kwargs):
		log_patient_action(request.user, 'doctor_hours_view')
		return super().retrieve(request, *args, **kwargs)

	def update(self, request, *args, **kwargs):
		response = super().update(request, *args, **kwargs)
		log_patient_action(request.user, 'doctor_hours_update')
		return response

	def destroy(self, request, *args, **kwargs):
		response = super().destroy(request, *args, **kwargs)
		log_patient_action(request.user, 'doctor_hours_delete')
		return response


class DoctorAbsenceListCreateView(generics.ListCreateAPIView):
	permission_classes = [DoctorAbsencePermission]
	serializer_class = DoctorAbsenceSerializer

	def get_queryset(self):
		qs = DoctorAbsence.objects.using('default').all()
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			return qs.filter(doctor=self.request.user)
		return qs

	def list(self, request, *args, **kwargs):
		log_patient_action(request.user, 'doctor_absence_list')
		return super().list(request, *args, **kwargs)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		log_patient_action(request.user, 'doctor_absence_create')
		headers = self.get_success_headers(serializer.data)
		return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class DoctorAbsenceDetailView(generics.RetrieveUpdateDestroyAPIView):
	permission_classes = [DoctorAbsencePermission]
	serializer_class = DoctorAbsenceSerializer

	def get_queryset(self):
		qs = DoctorAbsence.objects.using('default').all()
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			return qs.filter(doctor=self.request.user)
		return qs

	def retrieve(self, request, *args, **kwargs):
		log_patient_action(request.user, 'doctor_absence_view')
		return super().retrieve(request, *args, **kwargs)

	def update(self, request, *args, **kwargs):
		response = super().update(request, *args, **kwargs)
		log_patient_action(request.user, 'doctor_absence_update')
		return response

	def destroy(self, request, *args, **kwargs):
		response = super().destroy(request, *args, **kwargs)
		log_patient_action(request.user, 'doctor_absence_delete')
		return response


class DoctorBreakListCreateView(generics.ListCreateAPIView):
	permission_classes = [DoctorBreakPermission]
	serializer_class = DoctorBreakSerializer

	def get_queryset(self):
		qs = DoctorBreak.objects.using('default').all()
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			return qs.filter(doctor=self.request.user)
		return qs

	def list(self, request, *args, **kwargs):
		log_patient_action(request.user, 'doctor_break_list')
		return super().list(request, *args, **kwargs)

	def create(self, request, *args, **kwargs):
		serializer = self.get_serializer(data=request.data)
		serializer.is_valid(raise_exception=True)
		serializer.save()
		log_patient_action(request.user, 'doctor_break_create')
		headers = self.get_success_headers(serializer.data)
		return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class DoctorBreakDetailView(generics.RetrieveUpdateDestroyAPIView):
	permission_classes = [DoctorBreakPermission]
	serializer_class = DoctorBreakSerializer

	def get_queryset(self):
		qs = DoctorBreak.objects.using('default').all()
		role_name = getattr(getattr(self.request.user, 'role', None), 'name', None)
		if role_name == 'doctor':
			return qs.filter(doctor=self.request.user)
		return qs

	def retrieve(self, request, *args, **kwargs):
		log_patient_action(request.user, 'doctor_break_view')
		return super().retrieve(request, *args, **kwargs)

	def update(self, request, *args, **kwargs):
		response = super().update(request, *args, **kwargs)
		log_patient_action(request.user, 'doctor_break_update')
		return response

	def destroy(self, request, *args, **kwargs):
		response = super().destroy(request, *args, **kwargs)
		log_patient_action(request.user, 'doctor_break_delete')
		return response

# Create your views here.
