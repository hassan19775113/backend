from rest_framework import generics

from praxi_backend.core.utils import log_patient_action
from praxi_backend.patients.models import Patient
from praxi_backend.patients.permissions import PatientPermission
from praxi_backend.patients.serializers import PatientReadSerializer, PatientWriteSerializer


class PatientListCreateView(generics.ListCreateAPIView):
    """List all patients or create a new patient."""

    permission_classes = [PatientPermission]

    def get_queryset(self):
        return Patient.objects.using('default').all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PatientWriteSerializer
        return PatientReadSerializer

    def perform_create(self, serializer):
        obj = serializer.save()
        log_patient_action(
            self.request.user,
            'patient_created',
            patient_id=obj.patient_id,
        )


class PatientRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a patient."""

    permission_classes = [PatientPermission]

    def get_queryset(self):
        return Patient.objects.using('default').all()

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return PatientWriteSerializer
        return PatientReadSerializer

    def perform_update(self, serializer):
        obj = serializer.save()
        log_patient_action(
            self.request.user,
            'patient_updated',
            patient_id=obj.patient_id,
        )
