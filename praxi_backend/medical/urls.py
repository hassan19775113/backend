"""Medical App URLs - Legacy Patient Database (READ-ONLY).

Prefix: /api/medical/

NOTE: The medical database is READ-ONLY. Patient creation and updates
must be done via the patients app (system database cache) or through
the legacy system directly.

Routes:
    GET /api/medical/patients/           - List legacy patients
    GET /api/medical/patients/search/    - Search patients
    GET /api/medical/patients/<pk>/      - Retrieve patient details
"""

from django.urls import path

from praxi_backend.medical.views import (
    PatientDetailView,
    PatientListView,
    PatientSearchView,
)

app_name = 'medical'

urlpatterns = [
    path('patients/', PatientListView.as_view(), name='medical_patients_list'),
    path('patients/search/', PatientSearchView.as_view(), name='medical_patients_search'),
    path('patients/<int:pk>/', PatientDetailView.as_view(), name='medical_patients_detail'),
]
