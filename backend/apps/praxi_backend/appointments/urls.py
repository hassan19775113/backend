"""Appointments App URLs.

Prefix: /api/
Routes:
    /api/appointments/         - Termine
    /api/operations/           - OPs
    /api/calendar/             - Kalender-Ansichten
    /api/practice-hours/       - Praxis-Öffnungszeiten
    /api/doctor-hours/         - Arzt-Arbeitszeiten
    /api/doctor-absences/      - Arzt-Abwesenheiten
    /api/doctor-breaks/        - Arzt-Pausen
    /api/resources/            - Räume & Geräte
    /api/patient-flow/         - Patienten-Flow
    /api/op-dashboard/         - OP-Dashboard
    /api/op-timeline/          - OP-Timeline
    /api/op-stats/             - OP-Statistiken
"""

from django.urls import path
from praxi_backend.appointments.views import (  # Appointments; Calendar; Doctor scheduling; Operations; OP Dashboard & Timeline; OP Stats; Patient Flow; Practice Hours; Resources
    AppointmentDetailView,
    AppointmentListCreateView,
    AppointmentMarkNoShowView,
    AppointmentSuggestView,
    AppointmentTypeDetailView,
    AppointmentTypeListCreateView,
    AvailabilityView,
    CalendarDayView,
    CalendarMonthView,
    CalendarWeekView,
    DoctorAbsenceDetailView,
    DoctorAbsenceListCreateView,
    DoctorAbsencePreviewView,
    DoctorBreakDetailView,
    DoctorBreakListCreateView,
    DoctorHoursDetailView,
    DoctorHoursListCreateView,
    DoctorListView,
    OpDashboardLiveView,
    OpDashboardStatusUpdateView,
    OpDashboardView,
    OperationDetailView,
    OperationListCreateView,
    OperationSuggestView,
    OperationTypeDetailView,
    OperationTypeListCreateView,
    OpStatsDevicesView,
    OpStatsOverviewView,
    OpStatsRoomsView,
    OpStatsSurgeonsView,
    OpStatsTypesView,
    OpTimelineLiveView,
    OpTimelineRoomsView,
    OpTimelineView,
    PatientFlowDetailView,
    PatientFlowListCreateView,
    PatientFlowLiveView,
    PatientFlowStatusUpdateView,
    PracticeHoursDetailView,
    PracticeHoursListCreateView,
    ResourceCalendarResourcesView,
    ResourceCalendarView,
    ResourceDetailView,
    ResourceListCreateView,
)

app_name = "appointments"

urlpatterns = [
    # Appointments - WICHTIG: suggest VOR <int:pk>!
    path("appointments/", AppointmentListCreateView.as_view(), name="list"),
    path("appointments/suggest/", AppointmentSuggestView.as_view(), name="suggest"),
    # Doctors (MUSS VOR appointments/<int:pk>/ stehen!)
    path("appointments/doctors/", DoctorListView.as_view(), name="doctors_list"),
    path("appointments/<int:pk>/", AppointmentDetailView.as_view(), name="detail"),
    path(
        "appointments/<int:pk>/mark-no-show/",
        AppointmentMarkNoShowView.as_view(),
        name="mark_no_show",
    ),
    # Appointment Types
    path("appointment-types/", AppointmentTypeListCreateView.as_view(), name="types_list"),
    path("appointment-types/<int:pk>/", AppointmentTypeDetailView.as_view(), name="types_detail"),
    # Operations - WICHTIG: suggest VOR <int:pk>!
    path("operations/", OperationListCreateView.as_view(), name="operations_list"),
    path("operations/suggest/", OperationSuggestView.as_view(), name="operations_suggest"),
    path("operations/<int:pk>/", OperationDetailView.as_view(), name="operations_detail"),
    # Operation Types
    path("operation-types/", OperationTypeListCreateView.as_view(), name="operation_types_list"),
    path(
        "operation-types/<int:pk>/",
        OperationTypeDetailView.as_view(),
        name="operation_types_detail",
    ),
    path("op-dashboard/", OpDashboardView.as_view(), name="op_dashboard"),
    path("op-dashboard/live/", OpDashboardLiveView.as_view(), name="op_dashboard_live"),
    path(
        "op-dashboard/<int:pk>/status/",
        OpDashboardStatusUpdateView.as_view(),
        name="op_dashboard_status",
    ),
    path("op-timeline/", OpTimelineView.as_view(), name="op_timeline"),
    path("op-timeline/rooms/", OpTimelineRoomsView.as_view(), name="op_timeline_rooms"),
    path("op-timeline/live/", OpTimelineLiveView.as_view(), name="op_timeline_live"),
    path("resource-calendar/", ResourceCalendarView.as_view(), name="resource_calendar"),
    path(
        "resource-calendar/resources/",
        ResourceCalendarResourcesView.as_view(),
        name="resource_calendar_resources",
    ),
    path("patient-flow/", PatientFlowListCreateView.as_view(), name="patient_flow_list"),
    path("patient-flow/live/", PatientFlowLiveView.as_view(), name="patient_flow_live"),
    path("patient-flow/<int:pk>/", PatientFlowDetailView.as_view(), name="patient_flow_detail"),
    path(
        "patient-flow/<int:pk>/status/",
        PatientFlowStatusUpdateView.as_view(),
        name="patient_flow_status",
    ),
    path("op-stats/overview/", OpStatsOverviewView.as_view(), name="op_stats_overview"),
    path("op-stats/rooms/", OpStatsRoomsView.as_view(), name="op_stats_rooms"),
    path("op-stats/devices/", OpStatsDevicesView.as_view(), name="op_stats_devices"),
    path("op-stats/surgeons/", OpStatsSurgeonsView.as_view(), name="op_stats_surgeons"),
    path("op-stats/types/", OpStatsTypesView.as_view(), name="op_stats_types"),
    path("resources/", ResourceListCreateView.as_view(), name="resources_list"),
    path("resources/<int:pk>/", ResourceDetailView.as_view(), name="resources_detail"),
    path("calendar/day/", CalendarDayView.as_view(), name="calendar_day"),
    path("calendar/week/", CalendarWeekView.as_view(), name="calendar_week"),
    path("calendar/month/", CalendarMonthView.as_view(), name="calendar_month"),
    path("practice-hours/", PracticeHoursListCreateView.as_view(), name="practice_hours_list"),
    path(
        "practice-hours/<int:pk>/", PracticeHoursDetailView.as_view(), name="practice_hours_detail"
    ),
    path("doctor-hours/", DoctorHoursListCreateView.as_view(), name="doctor_hours_list"),
    path("doctor-hours/<int:pk>/", DoctorHoursDetailView.as_view(), name="doctor_hours_detail"),
    path("doctor-absences/", DoctorAbsenceListCreateView.as_view(), name="doctor_absences_list"),
    path(
        "doctor-absences/preview/",
        DoctorAbsencePreviewView.as_view(),
        name="doctor_absences_preview",
    ),
    path(
        "doctor-absences/<int:pk>/",
        DoctorAbsenceDetailView.as_view(),
        name="doctor_absences_detail",
    ),
    path("doctor-breaks/", DoctorBreakListCreateView.as_view(), name="doctor_breaks_list"),
    path("doctor-breaks/<int:pk>/", DoctorBreakDetailView.as_view(), name="doctor_breaks_detail"),
    # Doctors (Alias für direkten Zugriff ohne /appointments/ prefix)
    path("doctors/", DoctorListView.as_view(), name="doctors_list_alias"),
    # Availability
    path("availability/", AvailabilityView.as_view(), name="availability"),
]
