from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone
from praxi_backend.core.models import AuditLog, User
from praxi_backend.patients.utils import get_patient_display_name
from rest_framework import serializers

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
from .scheduling_facade import doctor_display_name
from .validators import (
    dedupe_int_list,
    resolve_active_devices,
    resolve_active_resources,
    validate_doctor_self_only,
    validate_doctor_user,
    validate_no_doctor_appointment_overlap_or_unavailable,
    validate_no_patient_appointment_overlap,
    validate_no_resource_conflicts,
    validate_patient_id,
    validate_time_range,
    validate_within_working_hours_or_unavailable,
)

ABSENCE_COLOR = "#FF4500"
BREAK_COLOR = "#FFD700"


class AppointmentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentType
        fields = [
            "id",
            "name",
            "color",
            "duration_minutes",
            "active",
            "created_at",
            "updated_at",
        ]


class AppointmentTypeNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppointmentType
        fields = ["id", "name", "color"]


class DoctorListSerializer(serializers.ModelSerializer):
    """Serializer für Arzt-Listen (nur Anzeigename, keine IDs sichtbar)."""

    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "calendar_color"]
        read_only_fields = fields

    def get_name(self, obj):
        """Holt den Anzeigenamen des Arztes."""
        return doctor_display_name(obj)


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = [
            "id",
            "name",
            "type",
            "color",
            "active",
            "created_at",
            "updated_at",
        ]


class AppointmentResourceSerializer(serializers.ModelSerializer):
    resource = ResourceSerializer(read_only=True)

    class Meta:
        model = AppointmentResource
        fields = ["id", "appointment", "resource"]


class PracticeHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = PracticeHours
        fields = [
            "id",
            "weekday",
            "start_time",
            "end_time",
            "active",
            "created_at",
            "updated_at",
        ]

    def validate_weekday(self, value):
        if value is None or not (0 <= int(value) <= 6):
            raise serializers.ValidationError(
                "Wochentag muss zwischen 0 (Montag) und 6 (Sonntag) liegen."
            )
        return value

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        if start_time is not None and end_time is not None and start_time >= end_time:
            raise serializers.ValidationError(
                {"end_time": "Endzeit muss nach der Startzeit liegen."}
            )
        return attrs


class DoctorHoursSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=User.objects.using("default").all())

    class Meta:
        model = DoctorHours
        fields = [
            "id",
            "doctor",
            "weekday",
            "start_time",
            "end_time",
            "active",
            "created_at",
            "updated_at",
        ]

    def validate_weekday(self, value):
        if value is None or not (0 <= int(value) <= 6):
            raise serializers.ValidationError(
                "Wochentag muss zwischen 0 (Montag) und 6 (Sonntag) liegen."
            )
        return value

    def validate(self, attrs):
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start_time is not None and end_time is not None and start_time >= end_time:
            raise serializers.ValidationError(
                {"end_time": "Endzeit muss nach der Startzeit liegen."}
            )
        return attrs


class DoctorAbsenceSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=User.objects.using("default").all())
    color = serializers.SerializerMethodField()

    class Meta:
        model = DoctorAbsence
        fields = [
            "id",
            "doctor",
            "start_date",
            "end_date",
            "reason",
            "color",
            "active",
            "created_at",
            "updated_at",
        ]

    def get_color(self, obj):
        return ABSENCE_COLOR

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date is not None and end_date is not None and start_date > end_date:
            raise serializers.ValidationError(
                {"end_date": "Enddatum muss am oder nach dem Startdatum liegen."}
            )
        return attrs


class DoctorBreakSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.using("default").all(),
        required=False,
        allow_null=True,
    )
    color = serializers.SerializerMethodField()

    class Meta:
        model = DoctorBreak
        fields = [
            "id",
            "doctor",
            "date",
            "start_time",
            "end_time",
            "reason",
            "color",
            "active",
            "created_at",
            "updated_at",
        ]

    def get_color(self, obj):
        return BREAK_COLOR

    def validate(self, attrs):
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start_time is not None and end_time is not None and start_time >= end_time:
            raise serializers.ValidationError(
                {"end_time": "Endzeit muss nach der Startzeit liegen."}
            )
        return attrs


class AppointmentSerializer(serializers.ModelSerializer):
    type = AppointmentTypeNestedSerializer(read_only=True)
    resources = ResourceSerializer(many=True, read_only=True)
    appointment_color = serializers.SerializerMethodField()
    doctor_color = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    doctor_name = serializers.SerializerMethodField()
    room_name = serializers.SerializerMethodField()
    resource_names = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "patient_id",
            "patient_name",
            "type",
            "doctor",
            "doctor_name",
            "resources",
            "room_name",
            "resource_names",
            "appointment_color",
            "doctor_color",
            "start_time",
            "end_time",
            "status",
            "is_no_show",
            "notes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = ["is_no_show"]

    def get_appointment_color(self, obj):
        type_obj = getattr(obj, "type", None)
        return getattr(type_obj, "color", None) if type_obj is not None else None

    def get_doctor_color(self, obj):
        doctor = getattr(obj, "doctor", None)
        return getattr(doctor, "calendar_color", None) if doctor is not None else None

    def get_patient_name(self, obj):
        """Holt den Anzeigenamen des Patienten (Name + Geburtsdatum)."""
        try:
            name_map = (self.context or {}).get("patient_name_map")
            if isinstance(name_map, dict):
                key = getattr(obj, "patient_id", None)
                if key in name_map:
                    return name_map.get(key) or ""
        except Exception:
            pass
        return get_patient_display_name(obj.patient_id)

    def get_doctor_name(self, obj):
        """Holt den Anzeigenamen des Arztes."""
        doctor = getattr(obj, "doctor", None)
        if doctor is None:
            return None
        return doctor_display_name(doctor)

    def get_room_name(self, obj):
        """Holt den Namen des ersten Raumes (Resource mit type='room')."""
        # If resources were prefetched, avoid per-object DB queries.
        try:
            cache = getattr(obj, "_prefetched_objects_cache", {}) or {}
            prefetched = cache.get("resources")
        except Exception:
            prefetched = None

        if prefetched is not None:
            for r in prefetched:
                if getattr(r, "active", False) and getattr(r, "type", None) == Resource.TYPE_ROOM:
                    return getattr(r, "name", None)
            return None

        room_resources = obj.resources.filter(type=Resource.TYPE_ROOM, active=True).first()
        return room_resources.name if room_resources else None

    def get_resource_names(self, obj):
        """Holt eine Liste aller Resource-Namen (außer Räume, die sind in room_name)."""
        try:
            cache = getattr(obj, "_prefetched_objects_cache", {}) or {}
            prefetched = cache.get("resources")
        except Exception:
            prefetched = None

        if prefetched is not None:
            return [
                getattr(r, "name", "")
                for r in prefetched
                if getattr(r, "active", False) and getattr(r, "type", None) != Resource.TYPE_ROOM
            ]

        resources = obj.resources.filter(active=True).exclude(type=Resource.TYPE_ROOM)
        return [resource.name for resource in resources]


class AppointmentCreateUpdateSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=User.objects.using("default").all())

    type = serializers.PrimaryKeyRelatedField(
        queryset=AppointmentType.objects.using("default").all(),
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
            "patient_id",
            "type",
            "doctor",
            "resource_ids",
            "start_time",
            "end_time",
            "status",
            "notes",
        ]

    def validate_patient_id(self, value):
        """Validate patient_id is a positive integer.

        NOTE: We do NOT validate patient existence here.
        patient_id is stored as an integer reference (not a FK).
        Existence validation should happen at API/business layer if needed.
        """
        return validate_patient_id(value)

    def validate(self, attrs):
        instance = getattr(self, "instance", None)

        request = self.context.get("request")

        start_time = attrs.get("start_time", getattr(instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(instance, "end_time", None))
        validate_time_range(start_time, end_time)

        doctor = attrs.get("doctor", getattr(instance, "doctor", None))
        validate_doctor_user(doctor, field_name="doctor")

        if request is not None:
            validate_doctor_self_only(request_user=getattr(request, "user", None), doctor=doctor)

        # Ressourcen validieren
        raw_resource_ids = attrs.get("resource_ids", None)
        resource_objs = None
        if raw_resource_ids is not None:
            unique_ids = dedupe_int_list(raw_resource_ids, field_name="resource_ids")
            resource_objs = resolve_active_resources(unique_ids)

            # Store resolved objects for create/update.
            attrs["_resource_objs"] = resource_objs

        # Arbeitszeiten-Konfliktprüfung
        # Reihenfolge: Erst Praxis, dann Arzt.
        if doctor is not None and start_time is not None and end_time is not None:
            validate_within_working_hours_or_unavailable(
                doctor=doctor, start_time=start_time, end_time=end_time
            )

        # Termin-Konfliktprüfung (Overlap Detection)
        # Overlap, wenn: start_time < existing.end_time AND end_time > existing.start_time
        if doctor is not None and start_time is not None and end_time is not None:
            validate_no_doctor_appointment_overlap_or_unavailable(
                doctor=doctor,
                start_time=start_time,
                end_time=end_time,
                exclude_appointment_id=(
                    getattr(instance, "id", None) if instance is not None else None
                ),
            )

        patient_id = attrs.get("patient_id", getattr(instance, "patient_id", None))

        # Ressourcen-Konfliktprüfung (Overlap Detection)
        # Nur prüfen, wenn resource_ids im Request gesetzt wurden.
        resource_objs = attrs.get("_resource_objs", None)
        if resource_objs is not None:
            validate_no_resource_conflicts(
                start_time=start_time,
                end_time=end_time,
                resources=resource_objs,
                exclude_appointment_id=(
                    getattr(instance, "id", None) if instance is not None else None
                ),
                request_user=getattr(request, "user", None) if request is not None else None,
                patient_id=patient_id,
            )

        if patient_id is not None and start_time is not None and end_time is not None:
            validate_no_patient_appointment_overlap(
                patient_id=int(patient_id),
                start_time=start_time,
                end_time=end_time,
                exclude_appointment_id=(
                    getattr(instance, "id", None) if instance is not None else None
                ),
            )

        return attrs

    # Resource conflicts are validated via praxi_backend.appointments.validators.

    def create(self, validated_data):
        resource_ids = validated_data.pop("resource_ids", None)
        resource_objs = validated_data.pop("_resource_objs", None)

        obj = super().create(validated_data)

        if resource_ids is not None:
            if resource_objs is None:
                resource_objs = list(
                    Resource.objects.using("default").filter(id__in=resource_ids, active=True)
                )

            AppointmentResource.objects.using("default").bulk_create(
                [AppointmentResource(appointment=obj, resource=r) for r in resource_objs],
                ignore_conflicts=True,
            )

        return obj

    def update(self, instance, validated_data):
        resource_ids = validated_data.pop("resource_ids", None)
        resource_objs = validated_data.pop("_resource_objs", None)

        obj = super().update(instance, validated_data)

        if resource_ids is not None:
            if resource_objs is None:
                resource_objs = list(
                    Resource.objects.using("default").filter(id__in=resource_ids, active=True)
                )

            AppointmentResource.objects.using("default").filter(appointment=obj).delete()
            AppointmentResource.objects.using("default").bulk_create(
                [AppointmentResource(appointment=obj, resource=r) for r in resource_objs],
                ignore_conflicts=True,
            )

        return obj


class OperationTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationType
        fields = [
            "id",
            "name",
            "prep_duration",
            "op_duration",
            "post_duration",
            "color",
            "active",
            "created_at",
            "updated_at",
        ]


class OperationTypeNestedSerializer(serializers.ModelSerializer):
    class Meta:
        model = OperationType
        fields = ["id", "name", "color", "prep_duration", "op_duration", "post_duration"]


class OperationSerializer(serializers.ModelSerializer):
    op_type = OperationTypeNestedSerializer(read_only=True)
    op_room = ResourceSerializer(read_only=True)
    op_devices = ResourceSerializer(many=True, read_only=True)
    team = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = Operation
        fields = [
            "id",
            "patient_id",
            "patient_name",
            "op_type",
            "op_room",
            "op_devices",
            "team",
            "start_time",
            "end_time",
            "color",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]

    def get_team(self, obj):
        def _u(u: User | None):
            if u is None:
                return None
            return {
                "id": u.id,
                "name": doctor_display_name(u),
                "color": getattr(u, "calendar_color", None),
            }

        return {
            "primary_surgeon": _u(getattr(obj, "primary_surgeon", None)),
            "assistant": _u(getattr(obj, "assistant", None)),
            "anesthesist": _u(getattr(obj, "anesthesist", None)),
        }

    def get_color(self, obj):
        t = getattr(obj, "op_type", None)
        return getattr(t, "color", None) if t is not None else None

    def get_patient_name(self, obj):
        if not getattr(obj, "patient_id", None):
            return ""
        try:
            name_map = (self.context or {}).get("patient_name_map")
            if isinstance(name_map, dict):
                key = getattr(obj, "patient_id", None)
                if key in name_map:
                    return name_map.get(key) or ""
        except Exception:
            pass
        return get_patient_display_name(obj.patient_id)


class OperationDashboardSerializer(serializers.ModelSerializer):
    type = OperationTypeNestedSerializer(source="op_type", read_only=True)
    room = ResourceSerializer(source="op_room", read_only=True)
    devices = ResourceSerializer(source="op_devices", many=True, read_only=True)
    team = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()

    class Meta:
        model = Operation
        fields = [
            "id",
            "type",
            "room",
            "devices",
            "team",
            "start_time",
            "end_time",
            "status",
            "progress",
            "color",
        ]

    def get_team(self, obj):
        def _u(u: User | None):
            if u is None:
                return None
            return {
                "id": u.id,
                "name": doctor_display_name(u),
                "color": getattr(u, "calendar_color", None),
            }

        return {
            "primary_surgeon": _u(getattr(obj, "primary_surgeon", None)),
            "assistant": _u(getattr(obj, "assistant", None)),
            "anesthesist": _u(getattr(obj, "anesthesist", None)),
        }

    def get_color(self, obj):
        t = getattr(obj, "op_type", None)
        return getattr(t, "color", None) if t is not None else None

    def get_progress(self, obj):
        if getattr(obj, "status", None) != Operation.STATUS_RUNNING:
            return 0.0
        start = getattr(obj, "start_time", None)
        end = getattr(obj, "end_time", None)
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
        fields = ["id", "name", "color"]


class RoomTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ["id", "name", "color"]


class OperationTimelineItemSerializer(serializers.ModelSerializer):
    type = OperationTypeTimelineSerializer(source="op_type", read_only=True)
    team = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()

    class Meta:
        model = Operation
        fields = [
            "id",
            "type",
            "team",
            "start_time",
            "end_time",
            "status",
            "progress",
            "color",
        ]

    def get_team(self, obj):
        def _u(u: User | None):
            if u is None:
                return None
            return {
                "id": u.id,
                "name": doctor_display_name(u),
                "color": getattr(u, "calendar_color", None),
            }

        return {
            "primary_surgeon": _u(getattr(obj, "primary_surgeon", None)),
            "assistant": _u(getattr(obj, "assistant", None)),
            "anesthesist": _u(getattr(obj, "anesthesist", None)),
        }

    def get_color(self, obj):
        t = getattr(obj, "op_type", None)
        return getattr(t, "color", None) if t is not None else None

    def get_progress(self, obj):
        # Same semantics as OperationDashboardSerializer.
        if getattr(obj, "status", None) != Operation.STATUS_RUNNING:
            return 0.0
        start = getattr(obj, "start_time", None)
        end = getattr(obj, "end_time", None)
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
    status = serializers.ChoiceField(
        choices=["running", "planned"], allow_null=True, required=False
    )
    progress = serializers.FloatField(required=False)


class ResourceCalendarColumnSerializer(serializers.Serializer):
    resource = ResourceSerializer()
    bookings = ResourceCalendarBookingSerializer(many=True)


def _allowed_patient_flow_transition(old: str, new: str) -> bool:
    transitions = {
        "registered": {"waiting"},
        "waiting": {"preparing"},
        "preparing": {"in_treatment"},
        "in_treatment": {"post_treatment"},
        "post_treatment": {"done"},
        "done": set(),
    }
    return new in transitions.get(old or "", set())


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
            "id",
            "appointment",
            "operation",
            "status",
            "arrival_time",
            "status_changed_at",
            "notes",
            "wait_time_minutes",
            "treatment_time_minutes",
        ]

    def _status_change_timestamps(self, obj):
        # Based on required audits: patient_flow_status_update.
        # We store flow_id + to-status in meta, then compute durations.
        qs = (
            AuditLog.objects.using("default")
            .filter(
                action="patient_flow_status_update",
                meta__flow_id=int(getattr(obj, "id", 0) or 0),
            )
            .order_by("timestamp", "id")
        )
        ts_by_to: dict[str, list] = {}
        for a in qs:
            meta = getattr(a, "meta", None) or {}
            to_status = meta.get("to")
            if not to_status:
                continue
            ts_by_to.setdefault(str(to_status), []).append(a.timestamp)
        return ts_by_to

    def get_wait_time_minutes(self, obj):
        arrival = getattr(obj, "arrival_time", None)
        if arrival is None:
            return None
        ts_by_to = self._status_change_timestamps(obj)
        # Wait time ends when treatment starts.
        in_tx = (ts_by_to.get("in_treatment") or [None])[0]
        if in_tx is None:
            # Still waiting/preparing etc -> time since arrival.
            now = timezone.now()
            return int(max(0, (now - arrival).total_seconds() // 60))
        return int(max(0, (in_tx - arrival).total_seconds() // 60))

    def get_treatment_time_minutes(self, obj):
        ts_by_to = self._status_change_timestamps(obj)
        in_tx = (ts_by_to.get("in_treatment") or [None])[0]
        if in_tx is None:
            return 0
        done_ts = (ts_by_to.get("done") or [None])[0]
        end = done_ts if done_ts is not None else timezone.now()
        return int(max(0, (end - in_tx).total_seconds() // 60))


class PatientFlowCreateUpdateSerializer(serializers.ModelSerializer):
    appointment_id = serializers.PrimaryKeyRelatedField(
        source="appointment",
        queryset=Appointment.objects.using("default").all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    operation_id = serializers.PrimaryKeyRelatedField(
        source="operation",
        queryset=Operation.objects.using("default").all(),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = PatientFlow
        fields = [
            "appointment_id",
            "operation_id",
            "status",
            "arrival_time",
            "notes",
        ]

    def validate(self, attrs):
        appt = attrs.get("appointment", getattr(self.instance, "appointment", None))
        op = attrs.get("operation", getattr(self.instance, "operation", None))
        if appt is None and op is None:
            raise serializers.ValidationError(
                {"non_field_errors": "Entweder Termin oder Operation muss gesetzt sein."}
            )

        old_status = (
            getattr(self.instance, "status", PatientFlow.STATUS_REGISTERED)
            if self.instance
            else None
        )
        new_status = attrs.get("status", old_status or PatientFlow.STATUS_REGISTERED)

        if (
            self.instance is not None
            and getattr(self.instance, "status", None) == PatientFlow.STATUS_DONE
        ):
            raise serializers.ValidationError({"status": '"done" ist schreibgeschützt.'})

        if old_status is not None and new_status != old_status:
            if not _allowed_patient_flow_transition(old_status, new_status):
                raise serializers.ValidationError(
                    {"status": f"Ungültiger Übergang {old_status} -> {new_status}."}
                )

        return attrs


class PatientFlowStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatientFlow
        fields = ["status"]

    def validate_status(self, value):
        inst = self.instance
        if inst is None:
            return value
        old = getattr(inst, "status", None)
        if old == PatientFlow.STATUS_DONE:
            raise serializers.ValidationError('"done" ist schreibgeschützt.')
        if value == old:
            return value
        if not _allowed_patient_flow_transition(old, value):
            raise serializers.ValidationError(f"Ungültiger Übergang {old} -> {value}.")
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
    primary_surgeon = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.using("default").all()
    )
    assistant = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.using("default").all(), required=False, allow_null=True
    )
    anesthesist = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.using("default").all(), required=False, allow_null=True
    )

    op_room = serializers.PrimaryKeyRelatedField(queryset=Resource.objects.using("default").all())
    op_device_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True, write_only=True
    )

    op_type = serializers.PrimaryKeyRelatedField(
        queryset=OperationType.objects.using("default").all()
    )

    end_time = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Operation
        fields = [
            "patient_id",
            "primary_surgeon",
            "assistant",
            "anesthesist",
            "op_room",
            "op_device_ids",
            "op_type",
            "start_time",
            "end_time",
            "status",
            "notes",
        ]

    def validate_patient_id(self, value):
        """Validate patient_id is a positive integer.

        NOTE: We do NOT validate patient existence here.
        patient_id is stored as an integer reference (not a FK).
        Existence validation should happen at API/business layer if needed.
        """
        return validate_patient_id(value)

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        request = self.context.get("request")

        start_time = attrs.get("start_time", getattr(instance, "start_time", None))
        if start_time is None:
            raise serializers.ValidationError({"start_time": "start_time ist ein Pflichtfeld."})

        op_type = attrs.get("op_type", getattr(instance, "op_type", None))
        if op_type is None:
            raise serializers.ValidationError({"op_type": "op_type ist ein Pflichtfeld."})
        if not getattr(op_type, "active", True):
            raise serializers.ValidationError({"op_type": "op_type ist inaktiv."})

        def _dur(x):
            # Kept local for now; larger conflict logic refactor will move this into validators.
            try:
                return max(0, int(x or 0))
            except Exception:
                return 0

        total_minutes = (
            _dur(getattr(op_type, "prep_duration", 0))
            + _dur(getattr(op_type, "op_duration", 0))
            + _dur(getattr(op_type, "post_duration", 0))
        )
        if total_minutes <= 0:
            raise serializers.ValidationError(
                {"detail": "Operation conflict", "reason": "invalid_duration"}
            )

        end_time = start_time + timedelta(minutes=total_minutes)
        attrs["end_time"] = end_time

        # Validate room
        room = attrs.get("op_room", getattr(instance, "op_room", None))
        if room is None:
            raise serializers.ValidationError({"op_room": "op_room ist ein Pflichtfeld."})
        if getattr(room, "type", None) != "room":
            raise serializers.ValidationError(
                {"op_room": 'op_room muss eine Ressource mit type="room" sein.'}
            )
        if not getattr(room, "active", True):
            raise serializers.ValidationError({"op_room": "op_room muss aktiv sein."})

        # Validate devices
        raw_device_ids = attrs.get("op_device_ids", None)
        device_objs = None
        if raw_device_ids is not None:
            unique = dedupe_int_list(raw_device_ids, field_name="op_device_ids")
            device_objs = resolve_active_devices(unique)
            attrs["_device_objs"] = device_objs

        # Team validation
        primary = attrs.get("primary_surgeon", getattr(instance, "primary_surgeon", None))
        assistant = attrs.get("assistant", getattr(instance, "assistant", None))
        anesth = attrs.get("anesthesist", getattr(instance, "anesthesist", None))

        # Team member validation
        validate_doctor_user(primary, field_name="primary_surgeon")
        validate_doctor_user(assistant, field_name="assistant")
        validate_doctor_user(anesth, field_name="anesthesist")
        if primary is not None and not getattr(primary, "is_active", True):
            raise serializers.ValidationError(
                {"primary_surgeon": "primary_surgeon muss aktiv sein."}
            )
        if assistant is not None and not getattr(assistant, "is_active", True):
            raise serializers.ValidationError({"assistant": "assistant muss aktiv sein."})
        if anesth is not None and not getattr(anesth, "is_active", True):
            raise serializers.ValidationError({"anesthesist": "anesthesist muss aktiv sein."})

        # RBAC: doctor cannot create/update others' ops
        if request is not None:
            req_user = getattr(request, "user", None)
            req_role = getattr(getattr(req_user, "role", None), "name", None)
            if req_role == "doctor":
                if primary is not None and getattr(primary, "id", None) != getattr(
                    req_user, "id", None
                ):
                    raise serializers.ValidationError(
                        {"detail": "Operation conflict", "reason": "doctor_self_only"}
                    )

        # Helper for conflicts
        def _raise_conflict(reason: str, meta: dict | None = None):
            # Phase 2E: no audit side-effects in serializers/validators.
            # Audit is triggered by the view/use-case layer when returning the 400.
            raise serializers.ValidationError({"detail": "Operation conflict", "reason": reason})

        # Room conflicts against other operations
        room_ops = Operation.objects.using("default").filter(
            op_room=room,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if instance is not None and getattr(instance, "id", None) is not None:
            room_ops = room_ops.exclude(id=instance.id)
        if room_ops.exists():
            _raise_conflict("room_conflict", {"room_id": room.id})

        # Room conflicts against appointments that booked the same resource
        appt_room = AppointmentResource.objects.using("default").filter(
            resource=room,
            appointment__start_time__lt=end_time,
            appointment__end_time__gt=start_time,
        )
        if appt_room.exists():
            _raise_conflict("room_conflict_with_appointments", {"room_id": room.id})

        # Device conflicts (ops + appointments)
        if device_objs is not None and device_objs:
            device_ids = [d.id for d in device_objs]
            dev_ops = OperationDevice.objects.using("default").filter(
                resource_id__in=device_ids,
                operation__start_time__lt=end_time,
                operation__end_time__gt=start_time,
            )
            if instance is not None and getattr(instance, "id", None) is not None:
                dev_ops = dev_ops.exclude(operation_id=instance.id)
            if dev_ops.exists():
                _raise_conflict("device_conflict", {"device_ids": device_ids})

            dev_appts = AppointmentResource.objects.using("default").filter(
                resource_id__in=device_ids,
                appointment__start_time__lt=end_time,
                appointment__end_time__gt=start_time,
            )
            if dev_appts.exists():
                _raise_conflict("device_conflict_with_appointments", {"device_ids": device_ids})

        # Surgeon/team conflicts with appointments + operations + absences + breaks + hours
        def _check_user_availability(user_obj: User | None, role_key: str):
            if user_obj is None:
                return

            local_start = (
                timezone.localtime(start_time) if timezone.is_aware(start_time) else start_time
            )
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

                if (
                    not PracticeHours.objects.using("default")
                    .filter(
                        weekday=weekday,
                        active=True,
                        start_time__lte=seg_start_t,
                        end_time__gte=seg_end_t,
                    )
                    .exists()
                ):
                    _raise_conflict("hours_conflict", {"who": role_key})

                if (
                    not DoctorHours.objects.using("default")
                    .filter(
                        doctor=user_obj,
                        weekday=weekday,
                        active=True,
                        start_time__lte=seg_start_t,
                        end_time__gte=seg_end_t,
                    )
                    .exists()
                ):
                    _raise_conflict("hours_conflict", {"who": role_key})

                day = day + timedelta(days=1)

            # Absences
            if (
                DoctorAbsence.objects.using("default")
                .filter(
                    doctor=user_obj,
                    active=True,
                    start_date__lte=end_date,
                    end_date__gte=start_date,
                )
                .exists()
            ):
                _raise_conflict("absence_conflict", {"who": role_key})

            # Breaks
            breaks = (
                DoctorBreak.objects.using("default")
                .filter(
                    active=True,
                    date__gte=start_date,
                    date__lte=end_date,
                )
                .filter(Q(doctor__isnull=True) | Q(doctor=user_obj))
            )

            if breaks.exists():
                tz = timezone.get_current_timezone()
                day = start_date
                while day <= end_date:
                    day_start_dt = timezone.make_aware(
                        datetime.combine(day, datetime.min.time()), tz
                    )
                    day_end_dt = timezone.make_aware(datetime.combine(day, datetime.max.time()), tz)
                    seg_start = max(local_start, day_start_dt)
                    seg_end = min(local_end, day_end_dt)

                    for br in breaks.filter(date=day):
                        br_start = timezone.make_aware(datetime.combine(day, br.start_time), tz)
                        br_end = timezone.make_aware(datetime.combine(day, br.end_time), tz)
                        if seg_start < br_end and seg_end > br_start:
                            _raise_conflict("break_conflict", {"who": role_key})
                    day = day + timedelta(days=1)

            # Appointments
            if (
                Appointment.objects.using("default")
                .filter(
                    doctor=user_obj,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                )
                .exists()
            ):
                _raise_conflict("appointment_conflict", {"who": role_key})

            # Operations
            op_q = (
                Operation.objects.using("default")
                .filter(
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                )
                .filter(
                    Q(primary_surgeon=user_obj) | Q(assistant=user_obj) | Q(anesthesist=user_obj)
                )
            )
            if instance is not None and getattr(instance, "id", None) is not None:
                op_q = op_q.exclude(id=instance.id)
            if op_q.exists():
                _raise_conflict("operation_conflict", {"who": role_key})

        _check_user_availability(primary, "primary_surgeon")
        _check_user_availability(assistant, "assistant")
        _check_user_availability(anesth, "anesthesist")

        return attrs

    def create(self, validated_data):
        device_ids = validated_data.pop("op_device_ids", None)
        device_objs = validated_data.pop("_device_objs", None)
        obj = super().create(validated_data)

        if device_ids is not None:
            if device_objs is None:
                device_objs = list(
                    Resource.objects.using("default").filter(
                        id__in=device_ids, active=True, type="device"
                    )
                )
            OperationDevice.objects.using("default").bulk_create(
                [OperationDevice(operation=obj, resource=r) for r in device_objs],
                ignore_conflicts=True,
            )
        return obj

    def update(self, instance, validated_data):
        device_ids = validated_data.pop("op_device_ids", None)
        device_objs = validated_data.pop("_device_objs", None)
        obj = super().update(instance, validated_data)

        if device_ids is not None:
            if device_objs is None:
                device_objs = list(
                    Resource.objects.using("default").filter(
                        id__in=device_ids, active=True, type="device"
                    )
                )
            OperationDevice.objects.using("default").filter(operation=obj).delete()
            OperationDevice.objects.using("default").bulk_create(
                [OperationDevice(operation=obj, resource=r) for r in device_objs],
                ignore_conflicts=True,
            )
        return obj
