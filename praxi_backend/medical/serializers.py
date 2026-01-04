"""Serializers for the medical app (legacy READ-ONLY database).

IMPORTANT: The medical database is READ-ONLY per architecture rules.
These serializers are used ONLY for reading patient data from the legacy DB.
Write operations (create/update) MUST NOT be performed on this database.
Use the patients app for patient data caching in the system database.
"""

from rest_framework import serializers

from praxi_backend.medical.models import Patient


class PatientSerializer(serializers.ModelSerializer):
    """Full patient data for admin/doctor/assistant roles."""

    class Meta:
        model = Patient
        fields = [
            'id',
            'first_name',
            'last_name',
            'birth_date',
            'gender',
            'phone',
            'email',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields  # All fields read-only


class PatientBillingSerializer(serializers.ModelSerializer):
    """Reduced patient data for billing role (no medical info)."""

    class Meta:
        model = Patient
        fields = [
            'id',
            'first_name',
            'last_name',
            'phone',
            'email',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields  # All fields read-only
