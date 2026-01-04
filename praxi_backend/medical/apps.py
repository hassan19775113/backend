"""
Medical App Configuration
"""

from django.apps import AppConfig


class MedicalConfig(AppConfig):
    """Standard App-Konfiguration für medizinische Daten"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'praxi_backend.medical'
    verbose_name = 'Medical (Medizinische Daten)'
