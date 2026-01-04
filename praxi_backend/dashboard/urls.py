"""
Dashboard URL Configuration
"""
from django.urls import path

from .views import DashboardView, DashboardAPIView
from .scheduling_views import SchedulingDashboardView, SchedulingAPIView
from .appointment_calendar_views import (
    AppointmentCalendarDayView,
    AppointmentCalendarWeekView,
    AppointmentCalendarMonthView,
)
from .patient_views import PatientDashboardView, PatientAPIView, PatientOverviewView
from .doctor_views import DoctorDashboardView, DoctorAPIView
from .operations_views import OperationsDashboardView, OperationsAPIView

app_name = 'dashboard'

urlpatterns = [
    # Haupt-Dashboard
    path('', DashboardView.as_view(), name='index'),
    path('api/', DashboardAPIView.as_view(), name='api'),
    
    # Scheduling Dashboard
    path('scheduling/', SchedulingDashboardView.as_view(), name='scheduling'),
    path('scheduling/api/', SchedulingAPIView.as_view(), name='scheduling_api'),

    # Termine (Kalenderansicht)
    path('appointments/', AppointmentCalendarDayView.as_view(), name='appointments_calendar_day'),
    path('appointments/week/', AppointmentCalendarWeekView.as_view(), name='appointments_calendar_week'),
    path('appointments/month/', AppointmentCalendarMonthView.as_view(), name='appointments_calendar_month'),
    
    # Patienten Dashboard
    path('patients/', PatientDashboardView.as_view(), name='patients'),
    path('patients/overview/', PatientOverviewView.as_view(), name='patients_overview'),
    path('patients/<int:patient_id>/', PatientDashboardView.as_view(), name='patient_detail'),
    path('patients/api/', PatientAPIView.as_view(), name='patients_api'),
    path('patients/api/<int:patient_id>/', PatientAPIView.as_view(), name='patient_api_detail'),
    
    # Ärzte Dashboard
    path('doctors/', DoctorDashboardView.as_view(), name='doctors'),
    path('doctors/<int:doctor_id>/', DoctorDashboardView.as_view(), name='doctor_detail'),
    path('doctors/api/', DoctorAPIView.as_view(), name='doctors_api'),
    path('doctors/api/<int:doctor_id>/', DoctorAPIView.as_view(), name='doctor_api_detail'),
    
    # Operations Dashboard
    path('operations/', OperationsDashboardView.as_view(), name='operations'),
    path('operations/api/', OperationsAPIView.as_view(), name='operations_api'),
]
