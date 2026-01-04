"""
Core App Configuration
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Standard App-Konfiguration für Core"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'praxi_backend.core'
    verbose_name = 'Core (Benutzer & Rollen)'