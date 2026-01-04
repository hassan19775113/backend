"""
Patients App - Admin für Patienten-Cache
"""

from django.contrib import admin
from django.utils.html import format_html

from praxi_backend.patients.models import Patient
from praxi_backend.core.admin import praxi_admin_site


@admin.register(Patient, site=praxi_admin_site)
class PatientAdmin(admin.ModelAdmin):
    """Admin für Patienten-Cache (lokale Kopie aus medical DB)"""
    
    list_display = (
        "id",
        "patient_id_badge",
        "full_name",
        "birth_date",
        "age_display",
        "created_at",
    )
    list_filter = ("created_at", "updated_at")
    search_fields = ("first_name", "last_name", "patient_id")
    ordering = ("last_name", "first_name")
    list_per_page = 50
    
    readonly_fields = ("id", "created_at", "updated_at")
    
    fieldsets = (
        ("👤 Patientendaten", {
            "fields": ("patient_id", "first_name", "last_name", "birth_date")
        }),
        ("📊 System", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def patient_id_badge(self, obj):
        """Patient-ID als Badge"""
        return format_html(
            '<span style="font-family: monospace; background-color: #1A73E8; '
            'color: white; padding: 2px 8px; border-radius: 4px;">#{}</span>',
            obj.patient_id
        )
    patient_id_badge.short_description = "Patient-ID"

    def full_name(self, obj):
        """Vollständiger Name"""
        return format_html(
            '<strong style="color: #1A73E8;">{}, {}</strong>',
            obj.last_name, obj.first_name
        )
    full_name.short_description = "Name"

    def age_display(self, obj):
        """Alter berechnen"""
        from datetime import date
        today = date.today()
        age = today.year - obj.birth_date.year - (
            (today.month, today.day) < (obj.birth_date.month, obj.birth_date.day)
        )
        return format_html('<span style="color: #5F6368;">{} Jahre</span>', age)
    age_display.short_description = "Alter"
