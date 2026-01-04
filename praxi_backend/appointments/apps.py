"""
Appointments App Configuration
"""

from django.apps import AppConfig


class AppointmentsConfig(AppConfig):
    """Standard App-Konfiguration für Termine & Planung"""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'praxi_backend.appointments'
    verbose_name = 'Appointments (Termine & Planung)'
