"""praxi_backend.medical.admin

Medical App - Admin classes (read-only)

The `medical.Patient` model is unmanaged (`managed = False`) and is expected to live
in a separate legacy database (alias: `medical`).

In dev/test environments, that database (or its `patients` table) may be missing.
To avoid 500 errors in the admin (e.g. `OperationalError: no such table: patients`),
we register the admin *only* when the `medical` DB exists and contains the expected table.
"""

from __future__ import annotations

from datetime import date

from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from django.db import connections

from praxi_backend.core.admin import praxi_admin_site

from .models import Patient



@admin.register(Patient, site=praxi_admin_site)
class PatientAdmin(admin.ModelAdmin):
    """Admin-Klasse für Patienten (Read-Only, legacy medical DB).

    If the `medical` database (or its `patients` table) is missing (common in dev
    SQLite setups), the changelist will show empty results instead of erroring.
    """

    list_display = (
        "id",
        "last_name",
        "first_name",
        "birth_date",
        "age_display",
        "gender_badge",
        "contact_info",
    )
    search_fields = ("last_name", "first_name", "phone", "email")
    list_filter = ("gender",)
    ordering = ("last_name", "first_name")
    list_per_page = 50

    readonly_fields = (
        "id",
        "first_name",
        "last_name",
        "birth_date",
        "gender",
        "phone",
        "email",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        (
            "📋 Patienteninformationen",
            {"fields": ("id", "first_name", "last_name", "birth_date", "gender")},
        ),
        ("📞 Kontaktdaten", {"fields": ("phone", "email")}),
        (
            "🕒 Systemdaten",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def _medical_table_available(self) -> bool:
        try:
            if "medical" not in connections:
                return False
            conn = connections["medical"]
            conn.ensure_connection()
            table_names = conn.introspection.table_names()
            return Patient._meta.db_table in set(table_names)
        except Exception:
            return False

    def get_queryset(self, request):
        # Avoid crashing the admin in dev when the legacy DB/table isn't present.
        if not self._medical_table_available():
            messages.warning(
                request,
                "Die Legacy Medical-DB (Alias 'medical') bzw. Tabelle 'patients' ist in dieser Umgebung nicht verfügbar. "
                "Die Patienten-Admin-Ansicht ist daher leer.",
            )
            return self.model.objects.none()

        # Always read from the legacy DB explicitly (avoid relying on routers).
        return super().get_queryset(request).using("medical")

    def has_add_permission(self, request):
        """Keine Patienten über Django Admin anlegen"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Keine Patienten über Django Admin löschen"""
        return False

    def has_change_permission(self, request, obj=None):
        """Nur Lesezugriff"""
        return True

    def gender_badge(self, obj):
        """Geschlecht als farbiges Badge"""
        if not obj.gender:
            return mark_safe('<span style="color: #9AA0A6;">—</span>')

        gender_map = {
            "male": ("👨", "#1A73E8", "Männlich"),
            "m": ("👨", "#1A73E8", "Männlich"),
            "female": ("👩", "#EA4335", "Weiblich"),
            "f": ("👩", "#EA4335", "Weiblich"),
            "w": ("👩", "#EA4335", "Weiblich"),
            "diverse": ("⚧", "#FBBC05", "Divers"),
            "d": ("⚧", "#FBBC05", "Divers"),
        }

        icon, color, label = gender_map.get(
            obj.gender.lower(),
            ("❓", "#5F6368", obj.gender),
        )

        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 3px 8px; border-radius: 4px; font-size: 11px;">{} {}</span>',
            color,
            icon,
            label,
        )

    gender_badge.short_description = "Geschlecht"

    def age_display(self, obj):
        """Alter berechnen"""
        if not obj.birth_date:
            return mark_safe('<span style="color: #9AA0A6;">—</span>')

        today = date.today()
        age = today.year - obj.birth_date.year
        if today.month < obj.birth_date.month or (
            today.month == obj.birth_date.month and today.day < obj.birth_date.day
        ):
            age -= 1

        if age < 18:
            color = "#FBBC05"
        elif age < 65:
            color = "#34A853"
        else:
            color = "#1A73E8"

        return format_html('<strong style="color: {}">{} Jahre</strong>', color, age)

    age_display.short_description = "Alter"

    def contact_info(self, obj):
        """Kontaktinformationen kompakt"""
        parts = []

        if obj.phone:
            parts.append(f"📞 {obj.phone}")

        if obj.email:
            parts.append(f"✉️ {obj.email}")

        if parts:
            return mark_safe("<br>".join(parts))

        return mark_safe('<span style="color: #9AA0A6;">—</span>')

    contact_info.short_description = "Kontakt"
