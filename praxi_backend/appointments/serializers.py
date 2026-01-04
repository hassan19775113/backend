from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from rest_framework import serializers

from praxi_backend.core.models import User, AuditLog
from praxi_backend.core.utils import log_patient_action

from .models import (
    Appointment,
    AppointmentResource,
    AppointmentType,
    DoctorAbsence,
    DoctorBreak,
    DoctorHours,
    PracticeHours,
    Resource,
    Operation,
    OperationDevice,
    OperationType,
	PatientFlow,
)
from .scheduling import compute_suggestions_for_doctor, doctor_display_name, get_active_doctors


ABSENCE_COLOR = "#FF4500"
BREAK_COLOR = "#FFD700"


class AppointmentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentType
        fields = [
            'id',
            'name',
            'color',
            'duration_minutes',
            'active',
            'created_at',
            'updated_at',
        ]


class AppointmentTypeNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentType
        fields = ['id', 'name', 'color']


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = [
            'id',
            'name',
            'type',
            'color',
            'active',
            'created_at',
            'updated_at',
        ]


class AppointmentResourceSerializer(serializers.ModelSerializer):
    resource = ResourceSerializer(read_only=True)

    class Meta:
        model = AppointmentResource
        fields = ['id', 'appointment', 'resource']


class PracticeHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = PracticeHours
        fields = [
            'id',
            'weekday',
            'start_time',
            'end_time',
            'active',
            'created_at',
            'updated_at',
        ]

    def validate_weekday(self, value):
        if value is None or not (0 <= int(value) <= 6):
            raise serializers.ValidationError('weekday must be between 0 (Monday) and 6 (Sunday).')
        return value

    def validate(self, attrs):
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        if start_time is not None and end_time is not None and start_time >= end_time:
            raise serializers.ValidationError({'end_time': 'end_time must be after start_time.'})
        return attrs


class DoctorHoursSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=User.objects.using('default').all())

    class Meta:
        model = DoctorHours
        fields = [
            'id',
            'doctor',
            'weekday',
            'start_time',
            'end_time',
            'active',
            'created_at',
            'updated_at',
        ]

    def validate_weekday(self, value):
        if value is None or not (0 <= int(value) <= 6):
            raise serializers.ValidationError('weekday must be between 0 (Monday) and 6 (Sunday).')
        return value

    def validate(self, attrs):
        start_time = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end_time = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        if start_time is not None and end_time is not None and start_time >= end_time:
            raise serializers.ValidationError({'end_time': 'end_time must be after start_time.'})
        return attrs


class DoctorAbsenceSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=User.objects.using('default').all())
    color = serializers.SerializerMethodField()

    class Meta:
        model = DoctorAbsence
        fields = [
            'id',
            'doctor',
            'start_date',
            'end_date',
            'reason',
            'color',
            'active',
            'created_at',
            'updated_at',
        ]

    def get_color(self, obj):
        return ABSENCE_COLOR

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start_date is not None and end_date is not None and start_date > end_date:
            raise serializers.ValidationError({'end_date': 'end_date must be on or after start_date.'})
        return attrs


class DoctorBreakSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.using('default').all(),
        required=False,
        allow_null=True,
    )
    color = serializers.SerializerMethodField()

    class Meta:
        model = DoctorBreak
        fields = [
            'id',
            'doctor',
            'date',
            'start_time',
            'end_time',
            'reason',
            'color',
            'active',
            'created_at',
            'updated_at',
        ]

    def get_color(self, obj):
        return BREAK_COLOR

    def validate(self, attrs):
        start_time = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end_time = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        if start_time is not None and end_time is not None and start_time >= end_time:
            raise serializers.ValidationError({'end_time': 'end_time must be after start_time.'})
        return attrs


class AppointmentSerializer(serializers.ModelSerializer):
    type = AppointmentTypeNestedSerializer(read_only=True)
    resources = ResourceSerializer(many=True, read_only=True)
    appointment_color = serializers.SerializerMethodField()
    doctor_color = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id',
            'patient_id',
            'type',
            'doctor',
            'resources',
            'appointment_color',
            'doctor_color',
            'start_time',
            'end_time',
            'status',
            'notes',
            'created_at',
            'updated_at',
        ]

    def get_appointment_color(self, obj):
        type_obj = getattr(obj, 'type', None)
        return getattr(type_obj, 'color', None) if type_obj is not None else None

    def get_doctor_color(self, obj):
        doctor = getattr(obj, 'doctor', None)
        return getattr(doctor, 'calendar_color', None) if doctor is not None else None


class AppointmentCreateUpdateSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.using('default').all()
    )

    type = serializers.PrimaryKeyRelatedField(
        queryset=AppointmentType.objects.using('default').all(),
        required=False,
        allow_null=True,
    )

    resource_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = Appointment
        fields = [
            'patient_id',
            'type',
            'doctor',
            'resource_ids',
            'start_time',
            'end_time',
            'status',
            'notes',
        ]

    def validate_patient_id(self, value):
        """Validate patient_id is a positive integer.
        
        NOTE: We do NOT query medical DB here per architecture rules.
        patient_id is stored as an integer reference, not a FK.
        Existence validation should happen at API/business layer if needed.
        """
        if value is None:
            raise serializers.ValidationError('patient_id ist ein Pflichtfeld.')
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError('patient_id muss eine Ganzzahl sein.')
        if value <= 0:
            raise serializers.ValidationError('patient_id muss positiv sein.')
        return value

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)

        request = self.context.get('request')

        def _duration_minutes(a: datetime, b: datetime) -> int:
            seconds = (b - a).total_seconds()
            minutes = int(seconds // 60)
            if seconds % 60:
                minutes += 1
            return max(1, minutes)

        def _alternatives_for(doctor_obj: User, start_day: timezone.datetime, duration_min: int):
            alts = []
            for rep in get_active_doctors(exclude_doctor_id=getattr(doctor_obj, 'id', None)):
                sug = compute_suggestions_for_doctor(
                    doctor=rep,
                    start_date=start_day.date(),
                    duration_minutes=duration_min,
                    limit=1,
                    type_obj=None,
                    max_days=31,
                )
                if sug:
                    alts.append(
                        {
                            'doctor': {'id': rep.id, 'name': doctor_display_name(rep)},
                            'next_available': sug[0]['start_time'],
                        }
                    )
            return alts

        def _raise_doctor_unavailable(doctor_obj: User, local_start_dt: datetime, local_end_dt: datetime):
            alts = _alternatives_for(doctor_obj, local_start_dt, _duration_minutes(local_start_dt, local_end_dt))
            raise serializers.ValidationError({'detail': 'Doctor unavailable.', 'alternatives': alts})

        start_time = attrs.get('start_time', getattr(instance, 'start_time', None))
        end_time = attrs.get('end_time', getattr(instance, 'end_time', None))
        if start_time is not None and end_time is not None and start_time >= end_time:
            raise serializers.ValidationError({'end_time': 'end_time muss nach start_time liegen.'})

        doctor = attrs.get('doctor', getattr(instance, 'doctor', None))
        if doctor is not None:
            role = getattr(doctor, 'role', None)
            if not role or getattr(role, 'name', None) != 'doctor':
                raise serializers.ValidationError({'doctor': 'doctor muss die Rolle "doctor" haben.'})

        if request is not None:
            user = getattr(request, 'user', None)
            user_role = getattr(getattr(user, 'role', None), 'name', None)
            if user_role == 'doctor' and doctor is not None and getattr(doctor, 'id', None) != getattr(user, 'id', None):
                raise serializers.ValidationError({'doctor': 'Ärzte dürfen nur eigene Termine anlegen/ändern.'})

        # Ressourcen validieren
        raw_resource_ids = attrs.get('resource_ids', None)
        resource_objs = None
        if raw_resource_ids is not None:
            unique_ids = []
            seen = set()
            for rid in raw_resource_ids:
                try:
                    rid_int = int(rid)
                except (TypeError, ValueError):
                    raise serializers.ValidationError({'resource_ids': 'resource_ids must be a list of integers.'})
                if rid_int not in seen:
                    seen.add(rid_int)
                    unique_ids.append(rid_int)

            if unique_ids:
                resource_objs = list(Resource.objects.using('default').filter(id__in=unique_ids, active=True).order_by('id'))
                found_ids = {r.id for r in resource_objs}
                missing = [rid for rid in unique_ids if rid not in found_ids]
                if missing:
                    raise serializers.ValidationError({'resource_ids': 'resource_ids contains unknown or inactive resource(s).'})
            else:
                resource_objs = []

            # Store resolved objects for create/update.
            attrs['_resource_objs'] = resource_objs

        # Arbeitszeiten-Konfliktprüfung
        # Reihenfolge: Erst Praxis, dann Arzt.
        if doctor is not None and start_time is not None and end_time is not None:
            # Normalize times to local timezone and make them offset-naive for safe comparison
            local_start = timezone.localtime(start_time) if timezone.is_aware(start_time) else start_time
            local_end = timezone.localtime(end_time) if timezone.is_aware(end_time) else end_time
            weekday = local_start.weekday()  # 0=Mon ... 6=Sun

            start_t = local_start.time().replace(tzinfo=None)
            end_t = local_end.time().replace(tzinfo=None)

            practice_qs = PracticeHours.objects.using('default').filter(weekday=weekday, active=True)
            if not practice_qs.exists():
                _raise_doctor_unavailable(doctor, local_start, local_end)

            practice_ok = practice_qs.filter(start_time__lte=start_t, end_time__gte=end_t).exists()
            if not practice_ok:
                _raise_doctor_unavailable(doctor, local_start, local_end)

            dh_qs = DoctorHours.objects.using('default').filter(doctor=doctor, weekday=weekday, active=True)
            if not dh_qs.exists():
                _raise_doctor_unavailable(doctor, local_start, local_end)

            dh_ok = dh_qs.filter(start_time__lte=start_t, end_time__gte=end_t).exists()
            if not dh_ok:
                _raise_doctor_unavailable(doctor, local_start, local_end)

            # Arzt-Abwesenheiten prüfen (Datumsspanne)
            appt_start_date = local_start.date()
            appt_end_date = local_end.date()
            absence_overlap = DoctorAbsence.objects.using('default').filter(
                doctor=doctor,
                active=True,
                start_date__lte=appt_end_date,
                end_date__gte=appt_start_date,
            ).exists()
            if absence_overlap:
                _raise_doctor_unavailable(doctor, local_start, local_end)

            # Pausen/Blockzeiten prüfen (praxisweit doctor=NULL oder arztbezogen)
            breaks = DoctorBreak.objects.using('default').filter(
                active=True,
                date__gte=appt_start_date,
                date__lte=appt_end_date,
            ).filter(
                Q(doctor__isnull=True) | Q(doctor=doctor)
            )

            if breaks.exists():
                tz = timezone.get_current_timezone()

                # Iterate days in range and check actual time overlap within each day.
                day = appt_start_date
                while day <= appt_end_date:
                    day_start_dt = timezone.make_aware(datetime.combine(day, datetime.min.time()), tz)
                    day_end_dt = timezone.make_aware(datetime.combine(day, datetime.max.time()), tz)

                    seg_start = max(local_start, day_start_dt)
                    seg_end = min(local_end, day_end_dt)

                    for br in breaks.filter(date=day):
                        br_start = timezone.make_aware(datetime.combine(day, br.start_time), tz)
                        br_end = timezone.make_aware(datetime.combine(day, br.end_time), tz)

                        if seg_start < br_end and seg_end > br_start:
                            _raise_doctor_unavailable(doctor, local_start, local_end)

                    day = day + timedelta(days=1)

        # Termin-Konfliktprüfung (Overlap Detection)
        # Overlap, wenn: start_time < existing.end_time AND end_time > existing.start_time
        if doctor is not None and start_time is not None and end_time is not None:
            doctor_conflicts = Appointment.objects.filter(
                doctor=doctor,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )
            if instance is not None and getattr(instance, 'id', None) is not None:
                doctor_conflicts = doctor_conflicts.exclude(id=instance.id)
            if doctor_conflicts.exists():
                local_start = timezone.localtime(start_time) if timezone.is_aware(start_time) else start_time
                local_end = timezone.localtime(end_time) if timezone.is_aware(end_time) else end_time
                _raise_doctor_unavailable(doctor, local_start, local_end)

        patient_id = attrs.get('patient_id', getattr(instance, 'patient_id', None))

        # Ressourcen-Konfliktprüfung (Overlap Detection)
        # Nur prüfen, wenn resource_ids im Request gesetzt wurden.
        resource_objs = attrs.get('_resource_objs', None)
        if resource_objs is not None:
            self._check_resource_conflicts(
                start_time=start_time,
                end_time=end_time,
                resource_objs=resource_objs,
                instance=instance,
                patient_id=patient_id,
            )

        if patient_id is not None and start_time is not None and end_time is not None:
            patient_conflicts = Appointment.objects.filter(
                patient_id=patient_id,
                start_time__lt=end_time,
                end_time__gt=start_time,
            )
            if instance is not None and getattr(instance, 'id', None) is not None:
                patient_conflicts = patient_conflicts.exclude(id=instance.id)
            if patient_conflicts.exists():
                raise serializers.ValidationError(
                    {
                        'detail': 'Appointment conflict: patient already has an appointment in this time range.'
                    }
                )

        return attrs

    def _check_resource_conflicts(self, *, start_time, end_time, resource_objs, instance, patient_id):
        if not resource_objs or start_time is None or end_time is None:
            return

        resource_ids = [r.id for r in resource_objs]
        qs = AppointmentResource.objects.using('default').filter(
            resource_id__in=resource_ids,
            appointment__start_time__lt=end_time,
            appointment__end_time__gt=start_time,
        )
        if instance is not None and getattr(instance, 'id', None) is not None:
            qs = qs.exclude(appointment_id=instance.id)

        conflict = qs.select_related('appointment', 'resource').order_by('id').first()
        conflict_meta = None
        if conflict is not None:
            conflict_meta = {
                'resource_id': conflict.resource_id,
                'appointment_id': conflict.appointment_id,
            }

        # Also block resources that are booked by operations (room + devices).
        if conflict_meta is None:
            room_ids = [r.id for r in resource_objs if getattr(r, 'type', None) == 'room']
            if room_ids:
                op = (
                    Operation.objects.using('default')
                    .filter(op_room_id__in=room_ids, start_time__lt=end_time, end_time__gt=start_time)
                    .order_by('start_time', 'id')
                    .first()
                )
                if op is not None:
                    conflict_meta = {
                        'resource_id': op.op_room_id,
                        'operation_id': op.id,
                        'reason': 'operation_room',
                    }

        if conflict_meta is None:
            device_ids = [r.id for r in resource_objs if getattr(r, 'type', None) == 'device']
            if device_ids:
                od = (
                    OperationDevice.objects.using('default')
                    .filter(resource_id__in=device_ids, operation__start_time__lt=end_time, operation__end_time__gt=start_time)
                    .select_related('operation')
                    .order_by('operation__start_time', 'operation_id', 'resource_id', 'id')
                    .first()
                )
                if od is not None:
                    conflict_meta = {
                        'resource_id': od.resource_id,
                        'operation_id': od.operation_id,
                        'reason': 'operation_device',
                    }

        if conflict_meta is None:
            return

        request = self.context.get('request')
        if request is not None:
            try:
                patient_id = int(patient_id) if patient_id is not None else None
            except Exception:
                patient_id = None
            log_patient_action(
                request.user,
                'resource_booking_conflict',
                patient_id,
                meta=conflict_meta,
            )

        raise serializers.ValidationError('Resource conflict')

    def create(self, validated_data):
        resource_ids = validated_data.pop('resource_ids', None)
        resource_objs = validated_data.pop('_resource_objs', None)

        obj = super().create(validated_data)

        if resource_ids is not None:
            if resource_objs is None:
                resource_objs = list(Resource.objects.using('default').filter(id__in=resource_ids, active=True))

            AppointmentResource.objects.using('default').bulk_create(
                [AppointmentResource(appointment=obj, resource=r) for r in resource_objs],
                ignore_conflicts=True,
            )

        return obj

    def update(self, instance, validated_data):
        resource_ids = validated_data.pop('resource_ids', None)
        resource_objs = validated_data.pop('_resource_objs', None)

        obj = super().update(instance, validated_data)

        if resource_ids is not None:
            if resource_objs is None:
                resource_objs = list(Resource.objects.using('default').filter(id__in=resource_ids, active=True))

            AppointmentResource.objects.using('default').filter(appointment=obj).delete()
            AppointmentResource.objects.using('default').bulk_create(
                [AppointmentResource(appointment=obj, resource=r) for r in resource_objs],
                ignore_conflicts=True,
            )

        return obj


class OperationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationType
        fields = [
            'id',
            'name',
            'prep_duration',
            'op_duration',
            'post_duration',
            'color',
            'active',
            'created_at',
            'updated_at',
        ]


class OperationTypeNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationType
        fields = ['id', 'name', 'color', 'prep_duration', 'op_duration', 'post_duration']


class OperationSerializer(serializers.ModelSerializer):
    op_type = OperationTypeNestedSerializer(read_only=True)
    op_room = ResourceSerializer(read_only=True)
    op_devices = ResourceSerializer(many=True, read_only=True)
    team = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()

    class Meta:
        model = Operation
        fields = [
            'id',
            'patient_id',
            'op_type',
            'op_room',
            'op_devices',
            'team',
            'start_time',
            'end_time',
            'color',
            'status',
            'notes',
            'created_at',
            'updated_at',
        ]

    def get_team(self, obj):
        def _u(u: User | None):
            if u is None:
                return None
            return {'id': u.id, 'name': doctor_display_name(u), 'color': getattr(u, 'calendar_color', None)}

        return {
            'primary_surgeon': _u(getattr(obj, 'primary_surgeon', None)),
            'assistant': _u(getattr(obj, 'assistant', None)),
            'anesthesist': _u(getattr(obj, 'anesthesist', None)),
        }

    def get_color(self, obj):
        t = getattr(obj, 'op_type', None)
        return getattr(t, 'color', None) if t is not None else None


class OperationDashboardSerializer(serializers.ModelSerializer):
    type = OperationTypeNestedSerializer(source='op_type', read_only=True)
    room = ResourceSerializer(source='op_room', read_only=True)
    devices = ResourceSerializer(source='op_devices', many=True, read_only=True)
    team = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()

    class Meta:
        model = Operation
        fields = [
            'id',
            'type',
            'room',
            'devices',
            'team',
            'start_time',
            'end_time',
            'status',
            'progress',
            'color',
        ]

    def get_team(self, obj):
        def _u(u: User | None):
            if u is None:
                return None
            return {'id': u.id, 'name': doctor_display_name(u), 'color': getattr(u, 'calendar_color', None)}

        return {
            'primary_surgeon': _u(getattr(obj, 'primary_surgeon', None)),
            'assistant': _u(getattr(obj, 'assistant', None)),
            'anesthesist': _u(getattr(obj, 'anesthesist', None)),
        }

    def get_color(self, obj):
        t = getattr(obj, 'op_type', None)
        return getattr(t, 'color', None) if t is not None else None

    def get_progress(self, obj):
        if getattr(obj, 'status', None) != Operation.STATUS_RUNNING:
            return 0.0
        start = getattr(obj, 'start_time', None)
        end = getattr(obj, 'end_time', None)
        if start is None or end is None:
            return 0.0
        total = (end - start).total_seconds()
        if total <= 0:
            return 0.0
        now = timezone.now()
        value = (now - start).total_seconds() / total
        if value < 0:
            value = 0.0
        if value > 1:
            value = 1.0
        return float(value)


class OperationTypeTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationType
        fields = ['id', 'name', 'color']


class RoomTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ['id', 'name', 'color']


class OperationTimelineItemSerializer(serializers.ModelSerializer):
    type = OperationTypeTimelineSerializer(source='op_type', read_only=True)
    team = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()

    class Meta:
        model = Operation
        fields = [
            'id',
            'type',
            'team',
            'start_time',
            'end_time',
            'status',
            'progress',
            'color',
        ]

    def get_team(self, obj):
        def _u(u: User | None):
            if u is None:
                return None
            return {'id': u.id, 'name': doctor_display_name(u), 'color': getattr(u, 'calendar_color', None)}

        return {
            'primary_surgeon': _u(getattr(obj, 'primary_surgeon', None)),
            'assistant': _u(getattr(obj, 'assistant', None)),
            'anesthesist': _u(getattr(obj, 'anesthesist', None)),
        }

    def get_color(self, obj):
        t = getattr(obj, 'op_type', None)
        return getattr(t, 'color', None) if t is not None else None

    def get_progress(self, obj):
        # Same semantics as OperationDashboardSerializer.
        if getattr(obj, 'status', None) != Operation.STATUS_RUNNING:
            return 0.0
        start = getattr(obj, 'start_time', None)
        end = getattr(obj, 'end_time', None)
        if start is None or end is None:
            return 0.0
        total = (end - start).total_seconds()
        if total <= 0:
            return 0.0
        now = timezone.now()
        value = (now - start).total_seconds() / total
        if value < 0:
            value = 0.0
        if value > 1:
            value = 1.0
        return float(value)


class OpTimelineGroupSerializer(serializers.Serializer):
    room = RoomTimelineSerializer()
    operations = OperationTimelineItemSerializer(many=True)


class ResourceCalendarBookingSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["appointment", "operation", "absence", "break"])
    id = serializers.IntegerField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    color = serializers.CharField(allow_null=True, required=False)
    label = serializers.CharField(allow_blank=True)
    status = serializers.ChoiceField(choices=["running", "planned"], allow_null=True, required=False)
    progress = serializers.FloatField(required=False)


class ResourceCalendarColumnSerializer(serializers.Serializer):
    resource = ResourceSerializer()
    bookings = ResourceCalendarBookingSerializer(many=True)


def _allowed_patient_flow_transition(old: str, new: str) -> bool:
    transitions = {
        'registered': {'waiting'},
        'waiting': {'preparing'},
        'preparing': {'in_treatment'},
        'in_treatment': {'post_treatment'},
        'post_treatment': {'done'},
        'done': set(),
    }
    return new in transitions.get(old or '', set())


class PatientFlowNestedAppointmentSerializer(AppointmentSerializer):
    class Meta(AppointmentSerializer.Meta):
        pass


class PatientFlowNestedOperationSerializer(OperationSerializer):
    class Meta(OperationSerializer.Meta):
        pass


class PatientFlowSerializer(serializers.ModelSerializer):
    appointment = PatientFlowNestedAppointmentSerializer(read_only=True)
    operation = PatientFlowNestedOperationSerializer(read_only=True)
    wait_time_minutes = serializers.SerializerMethodField()
    treatment_time_minutes = serializers.SerializerMethodField()

    class Meta:
        model = PatientFlow
        fields = [
            'id',
            'appointment',
            'operation',
            'status',
            'arrival_time',
            'status_changed_at',
            'notes',
            'wait_time_minutes',
            'treatment_time_minutes',
        ]

    def _status_change_timestamps(self, obj):
        # Based on required audits: patient_flow_status_update.
        # We store flow_id + to-status in meta, then compute durations.
        qs = AuditLog.objects.using('default').filter(
            action='patient_flow_status_update',
            meta__flow_id=int(getattr(obj, 'id', 0) or 0),
        ).order_by('timestamp', 'id')
        ts_by_to: dict[str, list] = {}
        for a in qs:
            meta = getattr(a, 'meta', None) or {}
            to_status = meta.get('to')
            if not to_status:
                continue
            ts_by_to.setdefault(str(to_status), []).append(a.timestamp)
        return ts_by_to

    def get_wait_time_minutes(self, obj):
        arrival = getattr(obj, 'arrival_time', None)
        if arrival is None:
            return None
        ts_by_to = self._status_change_timestamps(obj)
        # Wait time ends when treatment starts.
        in_tx = (ts_by_to.get('in_treatment') or [None])[0]
        if in_tx is None:
            # Still waiting/preparing etc -> time since arrival.
            now = timezone.now()
            return int(max(0, (now - arrival).total_seconds() // 60))
        return int(max(0, (in_tx - arrival).total_seconds() // 60))

    def get_treatment_time_minutes(self, obj):
        ts_by_to = self._status_change_timestamps(obj)
        in_tx = (ts_by_to.get('in_treatment') or [None])[0]
        if in_tx is None:
            return 0
        done_ts = (ts_by_to.get('done') or [None])[0]
        end = done_ts if done_ts is not None else timezone.now()
        return int(max(0, (end - in_tx).total_seconds() // 60))


class PatientFlowCreateUpdateSerializer(serializers.ModelSerializer):
    appointment_id = serializers.PrimaryKeyRelatedField(
        source='appointment',
        queryset=Appointment.objects.using('default').all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    operation_id = serializers.PrimaryKeyRelatedField(
        source='operation',
        queryset=Operation.objects.using('default').all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = PatientFlow
        fields = [
            'appointment_id',
            'operation_id',
            'status',
            'arrival_time',
            'notes',
        ]

    def validate(self, attrs):
        appt = attrs.get('appointment', getattr(self.instance, 'appointment', None))
        op = attrs.get('operation', getattr(self.instance, 'operation', None))
        if appt is None and op is None:
            raise serializers.ValidationError({'non_field_errors': 'Either appointment or operation must be set.'})

        old_status = getattr(self.instance, 'status', PatientFlow.STATUS_REGISTERED) if self.instance else None
        new_status = attrs.get('status', old_status or PatientFlow.STATUS_REGISTERED)

        if self.instance is not None and getattr(self.instance, 'status', None) == PatientFlow.STATUS_DONE:
            raise serializers.ValidationError({'status': 'done is read-only.'})

        if old_status is not None and new_status != old_status:
            if not _allowed_patient_flow_transition(old_status, new_status):
                raise serializers.ValidationError({'status': f'Invalid transition {old_status} -> {new_status}.'})

        return attrs


class PatientFlowStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientFlow
        fields = ['status']

    def validate_status(self, value):
        inst = self.instance
        if inst is None:
            return value
        old = getattr(inst, 'status', None)
        if old == PatientFlow.STATUS_DONE:
            raise serializers.ValidationError('done is read-only.')
        if value == old:
            return value
        if not _allowed_patient_flow_transition(old, value):
            raise serializers.ValidationError(f'Invalid transition {old} -> {value}.')
        return value


class OPStatsOverviewSerializer(serializers.Serializer):
    range_from = serializers.DateField()
    range_to = serializers.DateField()
    op_count = serializers.IntegerField()
    total_op_minutes = serializers.IntegerField()
    average_op_duration = serializers.FloatField()


class OPStatsRoomSerializer(serializers.Serializer):
    room = ResourceSerializer()
    total_minutes = serializers.IntegerField()
    used_minutes = serializers.IntegerField()
    utilization = serializers.FloatField()


class OPStatsDeviceSerializer(serializers.Serializer):
    device = ResourceSerializer()
    usage_minutes = serializers.IntegerField()


class OPStatsSurgeonSerializer(serializers.Serializer):
    surgeon = serializers.DictField()
    op_count = serializers.IntegerField()
    total_op_minutes = serializers.IntegerField()
    average_op_duration = serializers.FloatField()


class OPStatsTypeSerializer(serializers.Serializer):
    type = serializers.DictField()
    count = serializers.IntegerField()
    avg_duration = serializers.FloatField()
    min_duration = serializers.IntegerField()
    max_duration = serializers.IntegerField()


class OperationCreateUpdateSerializer(serializers.ModelSerializer):
    primary_surgeon = serializers.PrimaryKeyRelatedField(queryset=User.objects.using('default').all())
    assistant = serializers.PrimaryKeyRelatedField(queryset=User.objects.using('default').all(), required=False, allow_null=True)
    anesthesist = serializers.PrimaryKeyRelatedField(queryset=User.objects.using('default').all(), required=False, allow_null=True)

    op_room = serializers.PrimaryKeyRelatedField(queryset=Resource.objects.using('default').all())
    op_device_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True, write_only=True)

    op_type = serializers.PrimaryKeyRelatedField(queryset=OperationType.objects.using('default').all())

    end_time = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Operation
        fields = [
            'patient_id',
            'primary_surgeon',
            'assistant',
            'anesthesist',
            'op_room',
            'op_device_ids',
            'op_type',
            'start_time',
            'end_time',
            'status',
            'notes',
        ]

    def validate_patient_id(self, value):
        """Validate patient_id is a positive integer.
        
        NOTE: We do NOT query medical DB here per architecture rules.
        patient_id is stored as an integer reference, not a FK.
        Existence validation should happen at API/business layer if needed.
        """
        if value is None:
            raise serializers.ValidationError('patient_id ist ein Pflichtfeld.')
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError('patient_id muss eine Ganzzahl sein.')
        if value <= 0:
            raise serializers.ValidationError('patient_id muss positiv sein.')
        return value

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        request = self.context.get('request')

        start_time = attrs.get('start_time', getattr(instance, 'start_time', None))
        if start_time is None:
            raise serializers.ValidationError({'start_time': 'start_time ist ein Pflichtfeld.'})

        op_type = attrs.get('op_type', getattr(instance, 'op_type', None))
        if op_type is None:
            raise serializers.ValidationError({'op_type': 'op_type ist ein Pflichtfeld.'})
        if not getattr(op_type, 'active', True):
            raise serializers.ValidationError({'op_type': 'op_type ist inaktiv.'})

        def _dur(x):
            try:
                return max(0, int(x or 0))
            except Exception:
                return 0

        total_minutes = _dur(getattr(op_type, 'prep_duration', 0)) + _dur(getattr(op_type, 'op_duration', 0)) + _dur(getattr(op_type, 'post_duration', 0))
        if total_minutes <= 0:
            raise serializers.ValidationError({'detail': 'Operation conflict', 'reason': 'invalid_duration'})

        end_time = start_time + timedelta(minutes=total_minutes)
        attrs['end_time'] = end_time

        patient_id = attrs.get('patient_id', getattr(instance, 'patient_id', None))

        # Validate room
        room = attrs.get('op_room', getattr(instance, 'op_room', None))
        if room is None:
            raise serializers.ValidationError({'op_room': 'op_room ist ein Pflichtfeld.'})
        if getattr(room, 'type', None) != 'room':
            raise serializers.ValidationError({'op_room': 'op_room must be a Resource with type="room".'})
        if not getattr(room, 'active', True):
            raise serializers.ValidationError({'op_room': 'op_room must be active.'})

        # Validate devices
        raw_device_ids = attrs.get('op_device_ids', None)
        device_objs = None
        if raw_device_ids is not None:
            unique = []
            seen = set()
            for rid in raw_device_ids:
                try:
                    rid = int(rid)
                except (TypeError, ValueError):
                    raise serializers.ValidationError({'op_device_ids': 'op_device_ids must be a list of integers.'})
                if rid not in seen:
                    seen.add(rid)
                    unique.append(rid)

            if unique:
                device_objs = list(
                    Resource.objects.using('default')
                    .filter(id__in=unique, active=True, type='device')
                    .order_by('id')
                )
                found = {r.id for r in device_objs}
                missing = [rid for rid in unique if rid not in found]
                if missing:
                    raise serializers.ValidationError({'op_device_ids': 'op_device_ids contains unknown/inactive/non-device resource(s).'})
            else:
                device_objs = []
            attrs['_device_objs'] = device_objs

        # Team validation
        primary = attrs.get('primary_surgeon', getattr(instance, 'primary_surgeon', None))
        assistant = attrs.get('assistant', getattr(instance, 'assistant', None))
        anesth = attrs.get('anesthesist', getattr(instance, 'anesthesist', None))

        def _ensure_doctor(user_obj: User | None, field_name: str):
            if user_obj is None:
                return
            role = getattr(user_obj, 'role', None)
            if not role or getattr(role, 'name', None) != 'doctor':
                raise serializers.ValidationError({field_name: f'{field_name} muss die Rolle "doctor" haben.'})
            if not getattr(user_obj, 'is_active', True):
                raise serializers.ValidationError({field_name: f'{field_name} muss aktiv sein.'})

        _ensure_doctor(primary, 'primary_surgeon')
        _ensure_doctor(assistant, 'assistant')
        _ensure_doctor(anesth, 'anesthesist')

        # RBAC: doctor cannot create/update others' ops
        if request is not None:
            req_user = getattr(request, 'user', None)
            req_role = getattr(getattr(req_user, 'role', None), 'name', None)
            if req_role == 'doctor':
                if primary is not None and getattr(primary, 'id', None) != getattr(req_user, 'id', None):
                    raise serializers.ValidationError({'detail': 'Operation conflict', 'reason': 'doctor_self_only'})

        # Helper for conflicts
        def _raise_conflict(reason: str, meta: dict | None = None):
            if request is not None and not self.context.get('suppress_conflict_audit'):
                log_patient_action(
                    request.user,
                    'operation_conflict',
                    patient_id,
                    meta=meta or {'reason': reason},
                )
            raise serializers.ValidationError({'detail': 'Operation conflict', 'reason': reason})

        # Room conflicts against other operations
        room_ops = Operation.objects.using('default').filter(
            op_room=room,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if instance is not None and getattr(instance, 'id', None) is not None:
            room_ops = room_ops.exclude(id=instance.id)
        if room_ops.exists():
            _raise_conflict('room_conflict', {'room_id': room.id})

        # Room conflicts against appointments that booked the same resource
        appt_room = AppointmentResource.objects.using('default').filter(
            resource=room,
            appointment__start_time__lt=end_time,
            appointment__end_time__gt=start_time,
        )
        if appt_room.exists():
            _raise_conflict('room_conflict_with_appointments', {'room_id': room.id})

        # Device conflicts (ops + appointments)
        if device_objs is not None and device_objs:
            device_ids = [d.id for d in device_objs]
            dev_ops = OperationDevice.objects.using('default').filter(
                resource_id__in=device_ids,
                operation__start_time__lt=end_time,
                operation__end_time__gt=start_time,
            )
            if instance is not None and getattr(instance, 'id', None) is not None:
                dev_ops = dev_ops.exclude(operation_id=instance.id)
            if dev_ops.exists():
                _raise_conflict('device_conflict', {'device_ids': device_ids})

            dev_appts = AppointmentResource.objects.using('default').filter(
                resource_id__in=device_ids,
                appointment__start_time__lt=end_time,
                appointment__end_time__gt=start_time,
            )
            if dev_appts.exists():
                _raise_conflict('device_conflict_with_appointments', {'device_ids': device_ids})

        # Surgeon/team conflicts with appointments + operations + absences + breaks + hours
        def _check_user_availability(user_obj: User | None, role_key: str):
            if user_obj is None:
                return

            local_start = timezone.localtime(start_time) if timezone.is_aware(start_time) else start_time
            local_end = timezone.localtime(end_time) if timezone.is_aware(end_time) else end_time
            start_date = local_start.date()
            end_date = local_end.date()

            # Hours must cover entire block within each day
            tz = timezone.get_current_timezone()
            day = start_date
            while day <= end_date:
                day_start_dt = timezone.make_aware(datetime.combine(day, datetime.min.time()), tz)
                day_end_dt = timezone.make_aware(datetime.combine(day, datetime.max.time()), tz)
                seg_start = max(local_start, day_start_dt)
                seg_end = min(local_end, day_end_dt)
                weekday = day.weekday()
                seg_start_t = seg_start.time().replace(tzinfo=None)
                seg_end_t = seg_end.time().replace(tzinfo=None)

                if not PracticeHours.objects.using('default').filter(
                    weekday=weekday, active=True, start_time__lte=seg_start_t, end_time__gte=seg_end_t
                ).exists():
                    _raise_conflict('hours_conflict', {'who': role_key})

                if not DoctorHours.objects.using('default').filter(
                    doctor=user_obj, weekday=weekday, active=True, start_time__lte=seg_start_t, end_time__gte=seg_end_t
                ).exists():
                    _raise_conflict('hours_conflict', {'who': role_key})

                day = day + timedelta(days=1)

            # Absences
            if DoctorAbsence.objects.using('default').filter(
                doctor=user_obj,
                active=True,
                start_date__lte=end_date,
                end_date__gte=start_date,
            ).exists():
                _raise_conflict('absence_conflict', {'who': role_key})

            # Breaks
            breaks = DoctorBreak.objects.using('default').filter(
                active=True,
                date__gte=start_date,
                date__lte=end_date,
            ).filter(Q(doctor__isnull=True) | Q(doctor=user_obj))

            if breaks.exists():
                tz = timezone.get_current_timezone()
                day = start_date
                while day <= end_date:
                    day_start_dt = timezone.make_aware(datetime.combine(day, datetime.min.time()), tz)
                    day_end_dt = timezone.make_aware(datetime.combine(day, datetime.max.time()), tz)
                    seg_start = max(local_start, day_start_dt)
                    seg_end = min(local_end, day_end_dt)

                    for br in breaks.filter(date=day):
                        br_start = timezone.make_aware(datetime.combine(day, br.start_time), tz)
                        br_end = timezone.make_aware(datetime.combine(day, br.end_time), tz)
                        if seg_start < br_end and seg_end > br_start:
                            _raise_conflict('break_conflict', {'who': role_key})
                    day = day + timedelta(days=1)

            # Appointments
            if Appointment.objects.using('default').filter(
                doctor=user_obj,
                start_time__lt=end_time,
                end_time__gt=start_time,
            ).exists():
                _raise_conflict('appointment_conflict', {'who': role_key})

            # Operations
            op_q = Operation.objects.using('default').filter(
                start_time__lt=end_time,
                end_time__gt=start_time,
            ).filter(
                Q(primary_surgeon=user_obj) | Q(assistant=user_obj) | Q(anesthesist=user_obj)
            )
            if instance is not None and getattr(instance, 'id', None) is not None:
                op_q = op_q.exclude(id=instance.id)
            if op_q.exists():
                _raise_conflict('operation_conflict', {'who': role_key})

        _check_user_availability(primary, 'primary_surgeon')
        _check_user_availability(assistant, 'assistant')
        _check_user_availability(anesth, 'anesthesist')

        return attrs

    def create(self, validated_data):
        device_ids = validated_data.pop('op_device_ids', None)
        device_objs = validated_data.pop('_device_objs', None)
        obj = super().create(validated_data)

        if device_ids is not None:
            if device_objs is None:
                device_objs = list(Resource.objects.using('default').filter(id__in=device_ids, active=True, type='device'))
            OperationDevice.objects.using('default').bulk_create(
                [OperationDevice(operation=obj, resource=r) for r in device_objs],
                ignore_conflicts=True,
            )
        return obj

    def update(self, instance, validated_data):
        device_ids = validated_data.pop('op_device_ids', None)
        device_objs = validated_data.pop('_device_objs', None)
        obj = super().update(instance, validated_data)

        if device_ids is not None:
            if device_objs is None:
                device_objs = list(Resource.objects.using('default').filter(id__in=device_ids, active=True, type='device'))
            OperationDevice.objects.using('default').filter(operation=obj).delete()
            OperationDevice.objects.using('default').bulk_create(
                [OperationDevice(operation=obj, resource=r) for r in device_objs],
                ignore_conflicts=True,
            )
        return obj

