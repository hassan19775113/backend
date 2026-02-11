"""Appointment CRUD + suggest API views.

Moved from `praxi_backend.appointments.views` in Phase 2B.
No logic changes; only module split.
"""

from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone
from django.conf import settings
from praxi_backend.patients.utils import get_patient_display_name_map
from rest_framework import generics, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .exceptions import (
    DoctorAbsentError,
    DoctorBreakConflict,
    InvalidSchedulingData,
    SchedulingConflictError,
    SchedulingError,
    WorkingHoursViolation,
)
from .models import Appointment, AppointmentType, Resource
from .permissions import (
    AppointmentPermission,
    AppointmentSuggestPermission,
    AppointmentTypePermission,
)
from .scheduling_facade import (
    compute_suggestions_for_doctor,
    doctor_display_name,
    get_active_doctors,
)
from .scheduling_facade import plan_appointment as scheduling_plan_appointment
from .scheduling_facade import resolve_doctor
from .serializers import (
    AppointmentCreateUpdateSerializer,
    AppointmentSerializer,
    AppointmentTypeSerializer,
)
from .services.querying import apply_overlap_date_filters


def _log_patient_action(user, action: str, patient_id: int | None = None, meta: dict | None = None):
    """Route audit logging through `praxi_backend.appointments.views.log_patient_action`.

    Some tests patch `praxi_backend.appointments.views.log_patient_action`. After
    moving view classes into this module, we keep that patch point stable by
    resolving the function lazily from `views` at call time (avoids import cycles).
    """
    from . import views as views_module

    return views_module.log_patient_action(user, action, patient_id, meta=meta)


def _extract_patient_id_from_request(request) -> int | None:
    try:
        value = getattr(request, "data", {}).get("patient_id", None)
        return int(value) if value not in (None, "") else None
    except Exception:
        return None


def _maybe_audit_resource_conflict(*, request, exc: Exception) -> None:
    """Audit resource booking conflicts without putting side-effects in validators.

    The legacy validators raise a plain "Resource conflict" error string.
    Tests assert that such a failing POST writes an audit entry with action
    "resource_booking_conflict".
    """
    detail = getattr(exc, "detail", exc)
    if "Resource conflict" not in str(detail):
        return
    patient_id = _extract_patient_id_from_request(request)
    _log_patient_action(request.user, "resource_booking_conflict", patient_id)


class AppointmentListCreateView(generics.ListCreateAPIView):
    """List and create appointments.

    POST uses the scheduling service for full validation including:
    - Working hours validation
    - Doctor absence validation
    - Break validation
    - Conflict detection (doctor, room, device, patient)

    For GET requests (list), any authenticated user can view appointments.
    This is needed for the calendar view where users need to see appointments.

    For POST requests (create), AppointmentPermission applies (admin/assistant/doctor only).
    """

    use_scheduling_service = True  # Set to False to use legacy serializer-based validation
    pagination_class = None

    def get_permissions(self):
        """Use IsAuthenticated for GET, AppointmentPermission for POST/PUT/DELETE.

        For POST requests, we use IsAuthenticated if the user has no role,
        otherwise AppointmentPermission applies (admin/assistant/doctor only).
        """
        if self.request.method in ["GET", "HEAD", "OPTIONS"]:
            return [IsAuthenticated()]

        # Für POST/PUT/DELETE: Prüfe ob Benutzer eine Rolle hat
        user = getattr(self.request, "user", None)
        role_name = None
        if user and user.is_authenticated:
            role = getattr(user, "role", None)
            role_name = getattr(role, "name", None) if role else None

        # If a user has no role, allow POST only in DEBUG mode.
        # In production this would silently bypass RBAC.
        if not role_name and self.request.method == "POST" and getattr(settings, "DEBUG", False):
            return [IsAuthenticated()]

        # Ansonsten verwende AppointmentPermission (erfordert Rolle)
        return [AppointmentPermission()]

    def get_queryset(self):
        qs = (
            Appointment.objects.using("default")
            .select_related("doctor", "type")
            .prefetch_related("resources")
            .all()
        )

        role_name = getattr(getattr(self.request.user, "role", None), "name", None)
        if role_name == "doctor":
            return qs.filter(doctor=self.request.user)

        return qs

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AppointmentCreateUpdateSerializer
        return AppointmentSerializer

    def list(self, request, *args, **kwargs):
        """List appointments with optional date filtering.

        Supports optional query parameters:
        - date: YYYY-MM-DD format to filter appointments for a specific day
        - start_date: YYYY-MM-DD format for range start
        - end_date: YYYY-MM-DD format for range end

        Date filtering is timezone-aware to ensure appointments are correctly
        filtered regardless of UTC vs local time storage.
        """
        # Route through views.log_patient_action for stable patch point.
        _log_patient_action(request.user, "appointment_list")

        # Get base queryset + apply optional overlap filtering.
        qs = self.get_queryset()
        qs = apply_overlap_date_filters(
            qs,
            date_str=request.query_params.get("date"),
            start_date_str=request.query_params.get("start_date"),
            end_date_str=request.query_params.get("end_date"),
        )

        # Optional doctor filter (for calendar sidebar)
        doctor_id = request.query_params.get("doctor_id")
        if doctor_id:
            try:
                qs = qs.filter(doctor_id=int(doctor_id))
            except (TypeError, ValueError):
                pass

        # Apply ordering
        qs = qs.order_by("start_time", "id")

        # Build a patient name map once (avoids N+1 lookups in serializers).
        patient_name_map = {}
        try:
            patient_ids = list(qs.values_list("patient_id", flat=True))
            patient_name_map = get_patient_display_name_map(patient_ids)
        except Exception:
            patient_name_map = {}

        # Use pagination if configured
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer_class = self.get_serializer_class()
            context = self.get_serializer_context()
            context["patient_name_map"] = patient_name_map
            serializer = serializer_class(page, many=True, context=context)
            return self.get_paginated_response(serializer.data)

        serializer_class = self.get_serializer_class()
        context = self.get_serializer_context()
        context["patient_name_map"] = patient_name_map
        serializer = serializer_class(qs, many=True, context=context)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Create an appointment using the scheduling service.

        The scheduling service performs full validation and conflict detection.
        Scheduling exceptions are translated to appropriate HTTP responses.
        """
        if self.use_scheduling_service:
            return self._create_with_scheduling_service(request)
        return self._create_legacy(request)

    def _create_legacy(self, request):
        """Legacy create using serializer validation only."""
        write_serializer = self.get_serializer(data=request.data)
        try:
            write_serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as exc:
            _maybe_audit_resource_conflict(request=request, exc=exc)
            raise
        appointment = write_serializer.save()
        _log_patient_action(request.user, "appointment_create", appointment.patient_id)

        read_serializer = AppointmentSerializer(appointment, context={"request": request})
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def _create_with_scheduling_service(self, request):
        """Create using the scheduling service with full validation."""
        # First validate basic field structure with serializer
        write_serializer = self.get_serializer(data=request.data)
        try:
            write_serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as exc:
            _maybe_audit_resource_conflict(request=request, exc=exc)
            raise
        validated_data = write_serializer.validated_data

        # Extract doctor_id from validated doctor object
        doctor = validated_data.get("doctor")
        doctor_id = doctor.id if doctor else None

        # Build data dict for scheduling service
        scheduling_data = {
            "patient_id": validated_data.get("patient_id"),
            "doctor_id": doctor_id,
            "start_time": validated_data.get("start_time"),
            "end_time": validated_data.get("end_time"),
            "type_id": validated_data.get("type").id if validated_data.get("type") else None,
            "resource_ids": validated_data.get("resource_ids"),
            "status": validated_data.get("status", Appointment.STATUS_SCHEDULED),
            "notes": validated_data.get("notes", ""),
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
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        read_serializer = AppointmentSerializer(appointment, context={"request": request})
        # Ensure patient-related create actions are always audited, regardless of
        # whether we use the legacy serializer path or the scheduling service.
        _log_patient_action(request.user, "appointment_create", appointment.patient_id)
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AppointmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [AppointmentPermission]
    queryset = Appointment.objects.using("default").all()

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return AppointmentCreateUpdateSerializer
        return AppointmentSerializer

    def retrieve(self, request, *args, **kwargs):
        appointment = self.get_object()
        _log_patient_action(request.user, "appointment_view", appointment.patient_id)
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        appointment = self.get_object()

        write_serializer = AppointmentCreateUpdateSerializer(
            appointment,
            data=request.data,
            partial=partial,
            context={"request": request},
        )
        try:
            write_serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as exc:
            _maybe_audit_resource_conflict(request=request, exc=exc)
            raise
        updated = write_serializer.save()

        _log_patient_action(request.user, "appointment_update", updated.patient_id)
        read_serializer = AppointmentSerializer(updated, context={"request": request})
        return Response(read_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        appointment = self.get_object()
        patient_id = appointment.patient_id
        response = super().destroy(request, *args, **kwargs)
        _log_patient_action(request.user, "appointment_delete", patient_id)
        return response


class AppointmentMarkNoShowView(generics.GenericAPIView):
    """Mark an appointment as a confirmed no-show without changing status.

    Business rules:
    - Only past appointments are eligible.
    - Only statuses scheduled/confirmed can be marked.
    - Flag is idempotent; re-mark returns the current state.
    """

    permission_classes = [AppointmentPermission]
    queryset = (
        Appointment.objects.using("default")
        .select_related("doctor", "type")
        .prefetch_related("resources")
    )
    serializer_class = AppointmentSerializer

    def post(self, request, *args, **kwargs):
        appointment = self.get_object()
        self.check_object_permissions(request, appointment)

        now = timezone.now()

        if appointment.end_time >= now:
            return Response(
                {"detail": "No-Show kann nur für vergangene Termine gesetzt werden."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if appointment.status not in (
            Appointment.STATUS_SCHEDULED,
            Appointment.STATUS_CONFIRMED,
        ):
            return Response(
                {
                    "detail": "Nur Termine im Status scheduled/confirmed können als No-Show markiert werden.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not appointment.is_no_show:
            appointment.is_no_show = True
            appointment.save(update_fields=["is_no_show", "updated_at"])
            _log_patient_action(
                request.user,
                "appointment_mark_no_show",
                appointment.patient_id,
                meta={"appointment_id": appointment.id},
            )

        serializer = self.get_serializer(appointment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AppointmentSuggestView(generics.GenericAPIView):
    permission_classes = [AppointmentSuggestPermission]

    def _parse_iso_dt(self, value: str) -> datetime:
        # Accept 'Z' and offsets.
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        return datetime.fromisoformat(value)

    def _parse_int(self, request, key: str, *, required: bool = False, default=None):
        value = request.query_params.get(key)
        if value in (None, ""):
            if required:
                return None, Response(
                    {"detail": f"{key} query parameter is required."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return default, None
        try:
            return int(value), None
        except ValueError:
            return None, Response(
                {"detail": f"{key} must be an integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _parse_date(self, request, key: str, *, default_value: date):
        value = request.query_params.get(key)
        if value in (None, ""):
            return default_value, None
        try:
            return datetime.strptime(value, "%Y-%m-%d").date(), None
        except ValueError:
            return None, Response(
                {"detail": f"{key} must be in format YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def _parse_int_list(self, request, key: str):
        """Parse comma-separated list of ints.

        Examples:
        - ?resource_ids=1,2,3
        - ?resource_ids=
        """
        value = request.query_params.get(key)
        if value in (None, ""):
            return None, None
        parts = [p.strip() for p in str(value).split(",") if p.strip()]
        ids = []
        try:
            for p in parts:
                ids.append(int(p))
        except ValueError:
            return None, Response(
                {"detail": f"{key} must be a comma-separated list of integers."},
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
        doctor_id, err = self._parse_int(request, "doctor_id", required=True)
        if err is not None:
            return err

        type_id, err = self._parse_int(request, "type_id")
        if err is not None:
            return err

        duration_minutes, err = self._parse_int(request, "duration_minutes")
        if err is not None:
            return err

        start_date, err = self._parse_date(
            request, "start_date", default_value=timezone.localdate()
        )
        if err is not None:
            return err

        limit, err = self._parse_int(request, "limit", default=1)
        if err is not None:
            return err
        if limit is None or limit <= 0:
            return Response({"detail": "limit must be >= 1."}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve doctor
        doctor = resolve_doctor(doctor_id)
        if doctor is None:
            return Response({"detail": "doctor_id not found."}, status=status.HTTP_400_BAD_REQUEST)
        role_name = getattr(getattr(doctor, "role", None), "name", None)
        if role_name != "doctor":
            return Response(
                {"detail": 'doctor_id must reference a user with role "doctor".'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not getattr(doctor, "is_active", True):
            return Response(
                {"detail": "doctor_id must reference an active doctor."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Resolve type + duration
        type_obj = None
        if type_id is not None:
            type_obj = AppointmentType.objects.using("default").filter(id=type_id).first()
            if type_obj is None:
                return Response(
                    {"detail": "type_id not found."}, status=status.HTTP_400_BAD_REQUEST
                )
            if not getattr(type_obj, "active", True):
                return Response(
                    {"detail": "type_id is inactive."}, status=status.HTTP_400_BAD_REQUEST
                )

        if duration_minutes is None:
            if type_obj is None:
                return Response(
                    {"detail": "duration_minutes is required when type_id is not provided."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            duration_minutes = getattr(type_obj, "duration_minutes", None)
            if not duration_minutes:
                return Response(
                    {
                        "detail": "AppointmentType.duration_minutes is not set; provide duration_minutes."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if duration_minutes <= 0:
            return Response(
                {"detail": "duration_minutes must be >= 1."}, status=status.HTTP_400_BAD_REQUEST
            )

        resource_ids, err = self._parse_int_list(request, "resource_ids")
        if err is not None:
            return err

        resources = None
        if resource_ids is not None:
            resources = list(
                Resource.objects.using("default")
                .filter(id__in=resource_ids, active=True)
                .order_by("id")
            )
            found = {r.id for r in resources}
            missing = [rid for rid in resource_ids if rid not in found]
            if missing:
                return Response(
                    {"detail": "resource_ids contains unknown or inactive resource(s)."},
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
                            "doctor": {
                                "id": rep.id,
                                "name": doctor_display_name(rep),
                                "color": getattr(rep, "calendar_color", None),
                            },
                            "suggestions": rep_suggestions,
                            "_sort": self._parse_iso_dt(rep_suggestions[0]["start_time"]),
                        }
                    )

            items.sort(key=lambda x: x["_sort"])
            for item in items:
                item.pop("_sort", None)
            fallback_suggestions = items

        _log_patient_action(request.user, "appointment_suggest")
        if used_fallback and fallback_suggestions:
            _log_patient_action(request.user, "doctor_substitution_suggest")
        return Response(
            {
                "primary_doctor": {
                    "id": doctor.id,
                    "name": doctor_display_name(doctor),
                    "color": getattr(doctor, "calendar_color", None),
                },
                "primary_suggestions": primary_suggestions,
                "fallback_suggestions": fallback_suggestions,
            },
            status=status.HTTP_200_OK,
        )


class AppointmentTypeListCreateView(generics.ListCreateAPIView):
    """List/Create endpoint for appointment types.

    For GET requests (list), any authenticated user can view appointment types.
    This is needed for appointment creation/editing where users need to select a type.

    For POST requests (create), AppointmentTypePermission applies (admin/assistant only).
    """

    queryset = AppointmentType.objects.all()
    serializer_class = AppointmentTypeSerializer

    def get_permissions(self):
        """Use IsAuthenticated for GET, AppointmentTypePermission for POST/PUT/DELETE."""
        if self.request.method in ["GET", "HEAD", "OPTIONS"]:
            return [IsAuthenticated()]
        return [AppointmentTypePermission()]

    def get_queryset(self):
        """Filter appointment types by active status if requested."""
        queryset = AppointmentType.objects.using("default").all()

        # Filter nach active (wenn Parameter vorhanden)
        active_param = self.request.query_params.get("active", "").strip().lower()
        if active_param == "true":
            queryset = queryset.filter(active=True)
        elif active_param == "false":
            queryset = queryset.filter(active=False)

        return queryset.order_by("name", "id")

    def list(self, request, *args, **kwargs):
        _log_patient_action(request.user, "appointment_type_list")
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log_patient_action(request.user, "appointment_type_create")
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class AppointmentTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [AppointmentTypePermission]
    queryset = AppointmentType.objects.all()
    serializer_class = AppointmentTypeSerializer

    def retrieve(self, request, *args, **kwargs):
        _log_patient_action(request.user, "appointment_type_view")
        return super().retrieve(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        _log_patient_action(request.user, "appointment_type_update")
        return response

    def destroy(self, request, *args, **kwargs):
        r = super().destroy(request, *args, **kwargs)
        _log_patient_action(request.user, "appointment_type_delete")
        return r
