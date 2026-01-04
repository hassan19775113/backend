"""
Tests for Medical App (Legacy Patient Database)
"""

from django.test import TestCase


class MedicalModelTestCase(TestCase):
    """Basic tests for medical app models."""
    
    databases = {"default", "medical"}
    
    def test_patient_model_is_unmanaged(self):
        """Verify Patient model is unmanaged (read-only legacy DB)."""
        from praxi_backend.medical.models import Patient
        self.assertFalse(Patient._meta.managed)
        self.assertEqual(Patient._meta.db_table, 'patients')
