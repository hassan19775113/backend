"""Patients App URLs - Local Patient Cache (system DB).

Prefix: /api/
Routes:
    GET/POST    /api/patients/       - List/Create cached patients
    GET/PUT     /api/patients/<pk>/  - Retrieve/Update patient
"""

from django.urls import path

from praxi_backend.patients.views import (
    PatientListCreateView,
    PatientRetrieveUpdateView,
)

app_name = 'patients'

urlpatterns = [
    path('patients/', PatientListCreateView.as_view(), name='list'),
    path('patients/<int:pk>/', PatientRetrieveUpdateView.as_view(), name='detail'),
]
