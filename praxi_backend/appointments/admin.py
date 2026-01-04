"""
Appointments App - Vollständige Admin-Registrierung
Alle 12 Models mit Premium-Badges und Inlines
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import (
    Appointment,
    AppointmentResource,
    AppointmentType,
    DoctorAbsence,
    DoctorBreak,
    DoctorHours,
    Operation,
    OperationDevice,
    OperationType,
    PatientFlow,
    PracticeHours,
    Resource,
)
from praxi_backend.core.admin import praxi_admin_site


# ============================================================================
# Inline Classes
# ============================================================================
class AppointmentResourceInline(admin.TabularInline):
    """Inline für Termin-Ressourcen"""
    model = AppointmentResource
    extra = 0


class OperationDeviceInline(admin.TabularInline):
    """Inline für OP-Geräte"""
    model = OperationDevice
    extra = 0


class DoctorAbsenceInline(admin.TabularInline):
    """Inline für Arzt-Abwesenheiten"""
    model = DoctorAbsence
    extra = 0
    fields = ("start_date", "end_date", "reason", "active")


class DoctorBreakInline(admin.TabularInline):
    """Inline für Arzt-Pausen"""
    model = DoctorBreak
    extra = 0
    fields = ("date", "start_time", "end_time", "reason", "active")


class DoctorHoursInline(admin.TabularInline):
    """Inline für Arzt-Arbeitszeiten"""
    model = DoctorHours
    extra = 0
    fields = ("weekday", "start_time", "end_time", "active")


# ============================================================================
# AppointmentType Admin
# ============================================================================
@admin.register(AppointmentType, site=praxi_admin_site)
class AppointmentTypeAdmin(admin.ModelAdmin):
    """Admin für Termintypen"""
    
    list_display = ("name", "duration_badge", "color_preview", "active_badge", "created_at")
    list_filter = ("active", "created_at")
    search_fields = ("name",)
    ordering = ("name",)
    list_per_page = 50
    
    readonly_fields = ("id", "created_at", "updated_at")
    
    fieldsets = (
        ("📋 Termintyp", {
            "fields": ("name", "color", "duration_minutes", "active")
        }),
        ("📊 System", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def duration_badge(self, obj):
        """Dauer als Badge"""
        if not obj.duration_minutes:
            return mark_safe('<span style="color: #9AA0A6;">—</span>')
        
        if obj.duration_minutes < 30:
            color = "#34A853"
        elif obj.duration_minutes < 60:
            color = "#1A73E8"
        else:
            color = "#FBBC05"
        
        return format_html(
            '<span class="status-badge" style="background-color: {}; color: white;">'
            '⏱️ {} min</span>',
            color, obj.duration_minutes
        )
    duration_badge.short_description = "Dauer"

    def color_preview(self, obj):
        """Farbvorschau"""
        return format_html(
            '<div style="width: 30px; height: 20px; background-color: {}; '
            'border-radius: 4px; border: 1px solid #ccc;"></div>',
            obj.color or "#2E8B57"
        )
    color_preview.short_description = "Farbe"

    def active_badge(self, obj):
        """Aktiv-Status"""
        if obj.active:
            return mark_safe('<span class="status-badge" style="background-color: #34A853; color: white;">✅ Aktiv</span>')
        return mark_safe('<span class="status-badge" style="background-color: #9AA0A6; color: white;">⏸️ Inaktiv</span>')
    active_badge.short_description = "Status"


# ============================================================================
# PracticeHours Admin
# ============================================================================
@admin.register(PracticeHours, site=praxi_admin_site)
class PracticeHoursAdmin(admin.ModelAdmin):
    """Admin für Praxis-Öffnungszeiten"""
    
    WEEKDAY_NAMES = {
        0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
        4: "Freitag", 5: "Samstag", 6: "Sonntag"
    }
    
    list_display = ("weekday_display", "time_range", "active_badge")
    list_filter = ("weekday", "active")
    ordering = ("weekday", "start_time")
    list_per_page = 50
    
    readonly_fields = ("id", "created_at", "updated_at")
    
    fieldsets = (
        ("📅 Öffnungszeiten", {
            "fields": ("weekday", "start_time", "end_time", "active")
        }),
        ("📊 System", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def weekday_display(self, obj):
        """Wochentag als Text"""
        name = self.WEEKDAY_NAMES.get(obj.weekday, f"Tag {obj.weekday}")
        return format_html('<strong>{}</strong>', name)
    weekday_display.short_description = "Wochentag"

    def time_range(self, obj):
        """Zeitraum formatiert"""
        return format_html(
            '<span style="font-family: monospace; color: #1A73E8;">{} - {}</span>',
            obj.start_time.strftime("%H:%M"),
            obj.end_time.strftime("%H:%M")
        )
    time_range.short_description = "Öffnungszeit"

    def active_badge(self, obj):
        if obj.active:
            return mark_safe('<span style="color: #34A853;">✅ Aktiv</span>')
        return mark_safe('<span style="color: #9AA0A6;">⏸️ Inaktiv</span>')
    active_badge.short_description = "Status"


# ============================================================================
# DoctorHours Admin
# ============================================================================
@admin.register(DoctorHours, site=praxi_admin_site)
class DoctorHoursAdmin(admin.ModelAdmin):
    """Admin für Arzt-Arbeitszeiten"""
    
    WEEKDAY_NAMES = {
        0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"
    }
    
    list_display = ("doctor", "weekday_display", "time_range", "active_badge")
    list_filter = ("doctor", "weekday", "active")
    search_fields = ("doctor__username", "doctor__first_name", "doctor__last_name")
    ordering = ("doctor", "weekday", "start_time")
    list_per_page = 100
    
    readonly_fields = ("id", "created_at", "updated_at")

    def weekday_display(self, obj):
        return self.WEEKDAY_NAMES.get(obj.weekday, str(obj.weekday))
    weekday_display.short_description = "Tag"

    def time_range(self, obj):
        return format_html(
            '<span style="font-family: monospace;">{} - {}</span>',
            obj.start_time.strftime("%H:%M"),
            obj.end_time.strftime("%H:%M")
        )
    time_range.short_description = "Arbeitszeit"

    def active_badge(self, obj):
        if obj.active:
            return mark_safe('<span style="color: #34A853;">✅</span>')
        return mark_safe('<span style="color: #9AA0A6;">⏸️</span>')
    active_badge.short_description = "Aktiv"


# ============================================================================
# DoctorAbsence Admin
# ============================================================================
@admin.register(DoctorAbsence, site=praxi_admin_site)
class DoctorAbsenceAdmin(admin.ModelAdmin):
    """Admin für Arzt-Abwesenheiten"""
    
    list_display = ("doctor", "date_range", "reason_display", "active_badge")
    list_filter = ("doctor", "active", "start_date")
    search_fields = ("doctor__username", "doctor__first_name", "doctor__last_name", "reason")
    ordering = ("-start_date",)
    date_hierarchy = "start_date"
    list_per_page = 50
    
    readonly_fields = ("id", "created_at", "updated_at")
    
    fieldsets = (
        ("👨‍⚕️ Arzt", {
            "fields": ("doctor",)
        }),
        ("📅 Abwesenheit", {
            "fields": ("start_date", "end_date", "reason", "active")
        }),
        ("📊 System", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def date_range(self, obj):
        """Datumsbereich"""
        return format_html(
            '<span style="font-family: monospace;">{} → {}</span>',
            obj.start_date.strftime("%d.%m.%Y"),
            obj.end_date.strftime("%d.%m.%Y")
        )
    date_range.short_description = "Zeitraum"

    def reason_display(self, obj):
        if obj.reason:
            return obj.reason[:50] + "..." if len(obj.reason) > 50 else obj.reason
        return mark_safe('<span style="color: #9AA0A6; font-style: italic;">Kein Grund</span>')
    reason_display.short_description = "Grund"

    def active_badge(self, obj):
        if obj.active:
            return mark_safe('<span style="color: #34A853;">✅ Aktiv</span>')
        return mark_safe('<span style="color: #9AA0A6;">⏸️ Inaktiv</span>')
    active_badge.short_description = "Status"


# ============================================================================
# DoctorBreak Admin
# ============================================================================
@admin.register(DoctorBreak, site=praxi_admin_site)
class DoctorBreakAdmin(admin.ModelAdmin):
    """Admin für Arzt-Pausen"""
    
    list_display = ("date", "doctor_display", "time_range", "reason_display", "active_badge")
    list_filter = ("doctor", "active", "date")
    search_fields = ("doctor__username", "reason")
    ordering = ("-date", "start_time")
    date_hierarchy = "date"
    list_per_page = 50
    
    readonly_fields = ("id", "created_at", "updated_at")

    def doctor_display(self, obj):
        if obj.doctor:
            return obj.doctor.get_full_name() or obj.doctor.username
        return mark_safe('<span style="color: #1A73E8; font-weight: bold;">🏥 Praxisweit</span>')
    doctor_display.short_description = "Arzt"

    def time_range(self, obj):
        return format_html(
            '<span style="font-family: monospace;">{} - {}</span>',
            obj.start_time.strftime("%H:%M"),
            obj.end_time.strftime("%H:%M")
        )
    time_range.short_description = "Zeit"

    def reason_display(self, obj):
        if obj.reason:
            return obj.reason[:30] + "..." if len(obj.reason) > 30 else obj.reason
        return mark_safe('<span style="color: #9AA0A6;">—</span>')
    reason_display.short_description = "Grund"

    def active_badge(self, obj):
        if obj.active:
            return mark_safe('<span style="color: #34A853;">✅</span>')
        return mark_safe('<span style="color: #9AA0A6;">⏸️</span>')
    active_badge.short_description = "Aktiv"


# ============================================================================
# Appointment Admin (Enhanced with Inline)
# ============================================================================
@admin.register(Appointment, site=praxi_admin_site)
class AppointmentAdmin(admin.ModelAdmin):
    """Admin für Termine mit Ressourcen-Inline"""
    
    list_display = ("id", "patient_id", "doctor", "type", "time_display", "status_badge")
    list_filter = ("status", "doctor", "type", "start_time")
    search_fields = ("patient_id", "doctor__username", "notes")
    ordering = ("-start_time",)
    date_hierarchy = "start_time"
    list_per_page = 50
    
    inlines = [AppointmentResourceInline]
    
    readonly_fields = ("id", "created_at", "updated_at")
    
    fieldsets = (
        ("👤 Patient & Arzt", {
            "fields": ("patient_id", "doctor", "type")
        }),
        ("📅 Termin", {
            "fields": ("start_time", "end_time", "status")
        }),
        ("📝 Notizen", {
            "fields": ("notes",),
            "classes": ("collapse",)
        }),
        ("📊 System", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def time_display(self, obj):
        """Termin formatiert"""
        if not obj.start_time:
            return mark_safe('<span style="color: #9AA0A6;">—</span>')
        
        start = obj.start_time.strftime("%d.%m.%Y %H:%M")
        end = obj.end_time.strftime("%H:%M") if obj.end_time else "?"
        
        return format_html(
            '<div style="line-height: 1.4;">'
            '<span style="color: #1A73E8; font-weight: 600;">{}</span><br>'
            '<span style="color: #5F6368; font-size: 11px;">bis {}</span>'
            '</div>',
            start, end
        )
    time_display.short_description = "Zeitraum"

    def status_badge(self, obj):
        """Termin-Status als Badge"""
        status_map = {
            "scheduled": ("📅", "#1A73E8", "Geplant"),
            "confirmed": ("✔️", "#34A853", "Bestätigt"),
            "completed": ("✅", "#34A853", "Erledigt"),
            "cancelled": ("❌", "#EA4335", "Abgesagt"),
        }
        
        icon, color, label = status_map.get(
            obj.status,
            ("❓", "#5F6368", obj.status.upper())
        )
        
        return format_html(
            '<span class="status-badge" style="background-color: {}; color: white;">'
            '{} {}</span>',
            color, icon, label
        )
    status_badge.short_description = "Status"


# ============================================================================
# Resource Admin
# ============================================================================
@admin.register(Resource, site=praxi_admin_site)
class ResourceAdmin(admin.ModelAdmin):
    """Admin für Ressourcen (Räume & Geräte)"""
    
    list_display = ("name", "type_badge", "active_badge", "color_preview")
    list_filter = ("type", "active")
    search_fields = ("name",)
    ordering = ("type", "name")
    list_per_page = 50
    
    readonly_fields = ("id", "created_at", "updated_at")
    
    fieldsets = (
        ("🏥 Ressource", {
            "fields": ("name", "type", "color", "active")
        }),
        ("📊 System", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def type_badge(self, obj):
        """Ressourcentyp als Badge"""
        type_map = {
            "room": ("🏥", "#1A73E8", "Raum"),
            "device": ("🔬", "#34A853", "Gerät"),
        }
        
        icon, color, label = type_map.get(
            obj.type,
            ("❓", "#5F6368", obj.type.upper())
        )
        
        return format_html(
            '<span class="status-badge" style="background-color: {}; color: white;">'
            '{} {}</span>',
            color, icon, label
        )
    type_badge.short_description = "Typ"

    def active_badge(self, obj):
        """Aktiv-Status als Badge"""
        if obj.active:
            return mark_safe('<span style="color: #34A853;">✅ Aktiv</span>')
        return mark_safe('<span style="color: #9AA0A6;">⏸️ Inaktiv</span>')
    active_badge.short_description = "Status"

    def color_preview(self, obj):
        """Farbvorschau"""
        return format_html(
            '<div style="width: 30px; height: 20px; background-color: {}; '
            'border-radius: 4px; border: 1px solid #ccc;"></div>',
            obj.color
        )
    color_preview.short_description = "Farbe"


# ============================================================================
# AppointmentResource Admin
# ============================================================================
@admin.register(AppointmentResource, site=praxi_admin_site)
class AppointmentResourceAdmin(admin.ModelAdmin):
    """Admin für Termin-Ressourcen-Zuordnungen"""
    
    list_display = ("id", "appointment", "resource")
    list_filter = ("resource__type",)
    search_fields = ("appointment__id", "resource__name")
    ordering = ("-appointment__start_time",)
    list_per_page = 100
    
    readonly_fields = ("id",)


# ============================================================================
# OperationType Admin
# ============================================================================
@admin.register(OperationType, site=praxi_admin_site)
class OperationTypeAdmin(admin.ModelAdmin):
    """Admin für OP-Typen"""
    
    list_display = ("name", "duration_badge", "color_preview", "active_badge")
    search_fields = ("name",)
    list_filter = ("active",)
    ordering = ("name",)
    list_per_page = 50
    
    readonly_fields = ("id", "created_at", "updated_at")
    
    fieldsets = (
        ("🏥 OP-Typ", {
            "fields": ("name", "color", "active")
        }),
        ("⏱️ Dauern (Minuten)", {
            "fields": ("prep_duration", "op_duration", "post_duration")
        }),
        ("📊 System", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def duration_badge(self, obj):
        """Gesamtdauer mit Farbcodierung"""
        total = obj.prep_duration + obj.op_duration + obj.post_duration
        
        if total < 60:
            color = "#34A853"
        elif total < 120:
            color = "#1A73E8"
        else:
            color = "#EA4335"
        
        return format_html(
            '<span class="status-badge" style="background-color: {}; color: white;">'
            '⏱️ {} min</span><br>'
            '<span style="font-size: 10px; color: #5F6368;">Vor: {} | OP: {} | Nach: {}</span>',
            color, total, obj.prep_duration, obj.op_duration, obj.post_duration
        )
    duration_badge.short_description = "Dauer"

    def color_preview(self, obj):
        return format_html(
            '<div style="width: 30px; height: 20px; background-color: {}; '
            'border-radius: 4px; border: 1px solid #ccc;"></div>',
            obj.color
        )
    color_preview.short_description = "Farbe"

    def active_badge(self, obj):
        if obj.active:
            return mark_safe('<span style="color: #34A853;">✅ Aktiv</span>')
        return mark_safe('<span style="color: #9AA0A6;">⏸️ Inaktiv</span>')
    active_badge.short_description = "Status"


# ============================================================================
# Operation Admin (with Device Inline)
# ============================================================================
@admin.register(Operation, site=praxi_admin_site)
class OperationAdmin(admin.ModelAdmin):
    """Admin für Operationen mit Geräte-Inline"""
    
    list_display = (
        "id",
        "patient_id",
        "primary_surgeon",
        "op_type",
        "op_room",
        "time_display",
        "status_badge",
    )
    list_filter = ("status", "primary_surgeon", "op_type", "op_room", "start_time")
    search_fields = ("patient_id", "primary_surgeon__username", "notes")
    ordering = ("-start_time",)
    date_hierarchy = "start_time"
    list_per_page = 50
    
    inlines = [OperationDeviceInline]
    
    readonly_fields = ("id", "created_at", "updated_at")
    
    fieldsets = (
        ("👤 Patient", {
            "fields": ("patient_id",)
        }),
        ("👨‍⚕️ OP-Team", {
            "fields": ("primary_surgeon", "assistant", "anesthesist")
        }),
        ("🏥 OP-Details", {
            "fields": ("op_type", "op_room")
        }),
        ("📅 Zeitraum", {
            "fields": ("start_time", "end_time", "status")
        }),
        ("📝 Notizen", {
            "fields": ("notes",),
            "classes": ("collapse",)
        }),
        ("📊 System", {
            "fields": ("id", "created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )

    def time_display(self, obj):
        if not obj.start_time:
            return mark_safe('<span style="color: #9AA0A6;">—</span>')
        
        start = obj.start_time.strftime("%d.%m.%Y %H:%M")
        end = obj.end_time.strftime("%H:%M") if obj.end_time else "?"
        
        return format_html(
            '<div style="line-height: 1.4;">'
            '<span style="color: #1A73E8; font-weight: 600;">{}</span><br>'
            '<span style="color: #5F6368; font-size: 11px;">bis {}</span>'
            '</div>',
            start, end
        )
    time_display.short_description = "Zeitraum"

    def status_badge(self, obj):
        status_map = {
            "planned": ("📋", "#5F6368", "Geplant"),
            "confirmed": ("✔️", "#1A73E8", "Bestätigt"),
            "running": ("🔴", "#EA4335", "Läuft"),
            "done": ("✅", "#34A853", "Erledigt"),
            "cancelled": ("❌", "#9AA0A6", "Abgesagt"),
        }
        
        icon, color, label = status_map.get(
            obj.status,
            ("❓", "#5F6368", obj.status.upper())
        )
        
        return format_html(
            '<span class="status-badge" style="background-color: {}; color: white;">'
            '{} {}</span>',
            color, icon, label
        )
    status_badge.short_description = "Status"


# ============================================================================
# OperationDevice Admin
# ============================================================================
@admin.register(OperationDevice, site=praxi_admin_site)
class OperationDeviceAdmin(admin.ModelAdmin):
    """Admin für OP-Geräte-Zuordnungen"""
    
    list_display = ("id", "operation", "resource")
    list_filter = ("resource",)
    search_fields = ("operation__id", "resource__name")
    ordering = ("-operation__start_time",)
    list_per_page = 100
    
    readonly_fields = ("id",)


# ============================================================================
# PatientFlow Admin
# ============================================================================
@admin.register(PatientFlow, site=praxi_admin_site)
class PatientFlowAdmin(admin.ModelAdmin):
    """Admin für Patienten-Flow (Wartezeiten & Status)"""
    
    list_display = (
        "id",
        "appointment_display",
        "operation_display",
        "status_badge",
        "arrival_time_display",
        "status_changed_at",
    )
    list_filter = ("status", "status_changed_at")
    search_fields = ("appointment__id", "operation__id", "notes")
    ordering = ("-status_changed_at",)
    date_hierarchy = "status_changed_at"
    list_per_page = 50
    
    readonly_fields = ("id", "status_changed_at")
    
    fieldsets = (
        ("📋 Referenz", {
            "fields": ("appointment", "operation")
        }),
        ("🚶 Patienten-Status", {
            "fields": ("status", "arrival_time")
        }),
        ("📝 Notizen", {
            "fields": ("notes",),
            "classes": ("collapse",)
        }),
        ("📊 System", {
            "fields": ("id", "status_changed_at"),
            "classes": ("collapse",)
        }),
    )

    def appointment_display(self, obj):
        if obj.appointment:
            return format_html(
                '<a href="/praxiadmin/appointments/appointment/{}/change/" '
                'style="color: #1A73E8;">Termin #{}</a>',
                obj.appointment.id, obj.appointment.id
            )
        return mark_safe('<span style="color: #9AA0A6;">—</span>')
    appointment_display.short_description = "Termin"

    def operation_display(self, obj):
        if obj.operation:
            return format_html(
                '<a href="/praxiadmin/appointments/operation/{}/change/" '
                'style="color: #1A73E8;">OP #{}</a>',
                obj.operation.id, obj.operation.id
            )
        return mark_safe('<span style="color: #9AA0A6;">—</span>')
    operation_display.short_description = "Operation"

    def status_badge(self, obj):
        status_map = {
            "registered": ("📝", "#5F6368", "Angemeldet"),
            "waiting": ("⏳", "#FBBC05", "Wartend"),
            "preparing": ("🔧", "#1A73E8", "Vorbereitung"),
            "in_treatment": ("🏥", "#EA4335", "In Behandlung"),
            "post_treatment": ("🩹", "#9334E6", "Nachbehandlung"),
            "done": ("✅", "#34A853", "Fertig"),
        }
        
        icon, color, label = status_map.get(
            obj.status,
            ("❓", "#5F6368", obj.status.upper())
        )
        
        return format_html(
            '<span class="status-badge" style="background-color: {}; color: white;">'
            '{} {}</span>',
            color, icon, label
        )
    status_badge.short_description = "Status"

    def arrival_time_display(self, obj):
        if obj.arrival_time:
            return obj.arrival_time.strftime("%d.%m.%Y %H:%M")
        return mark_safe('<span style="color: #9AA0A6;">—</span>')
    arrival_time_display.short_description = "Ankunft"
