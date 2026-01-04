"""
PraxiApp - Custom Admin Site & Admin Classes
Medizinisches Premium-Branding mit Custom AdminSite
"""

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import AuditLog, Role, User


# ============================================================================
# Custom AdminSite für PraxiApp
# ============================================================================
class PraxiAdminSite(AdminSite):
    """Custom Admin Site für PraxiApp mit medizinischem Branding"""
    site_header = "🏥 PraxiApp – Medizinisches Cockpit"
    site_title = "PraxiApp Admin"
    index_title = "Systemübersicht"
    site_url = None
    
    def each_context(self, request):
        """Zusätzlicher Kontext für alle Admin-Seiten"""
        context = super().each_context(request)
        context['site_subtitle'] = 'Praxis & OP Management System'
        context['site_version'] = 'v1.0.0'
        context['dashboard_url'] = '/praxiadmin/dashboard/'
        context['scheduling_dashboard_url'] = '/praxiadmin/dashboard/scheduling/'
        return context
    
    def get_app_list(self, request, app_label=None):
        """Fügt Dashboards als erste Menüpunkte hinzu"""
        app_list = super().get_app_list(request, app_label)
        
        # Dashboards als erstes Element hinzufügen
        dashboard_app = {
            'name': '📊 Dashboards',
            'app_label': 'dashboard',
            'app_url': '/praxiadmin/dashboard/',
            'has_module_perms': True,
            'models': [
                {
                    'name': '📊 Haupt-Dashboard',
                    'object_name': 'Dashboard',
                    'admin_url': '/praxiadmin/dashboard/',
                    'view_only': True,
                },
                {
                    'name': '📈 Scheduling KPIs',
                    'object_name': 'SchedulingDashboard',
                    'admin_url': '/praxiadmin/dashboard/scheduling/',
                    'view_only': True,
                },
                {
                    'name': '👤 Patienten-Dashboard',
                    'object_name': 'PatientDashboard',
                    'admin_url': '/praxiadmin/dashboard/patients/',
                    'view_only': True,
                },
                {
                    'name': '👨‍⚕️ Ärzte-Dashboard',
                    'object_name': 'DoctorDashboard',
                    'admin_url': '/praxiadmin/dashboard/doctors/',
                    'view_only': True,
                },
                {
                    'name': '⚙️ Operations-Dashboard',
                    'object_name': 'OperationsDashboard',
                    'admin_url': '/praxiadmin/dashboard/operations/',
                    'view_only': True,
                },
            ],
        }
        
        return [dashboard_app] + app_list


# Globale Instanz der Custom AdminSite
praxi_admin_site = PraxiAdminSite(name='praxiadmin')


# ============================================================================
# Role Admin
# ============================================================================
@admin.register(Role, site=praxi_admin_site)
class RoleAdmin(admin.ModelAdmin):
    """Admin-Klasse für Rollen"""
    
    list_display = ("name", "label", "user_count_badge")
    search_fields = ("name", "label")
    ordering = ("name",)
    list_per_page = 50
    
    fieldsets = (
        ("📋 Rollen-Informationen", {
            "fields": ("name", "label")
        }),
    )

    def user_count_badge(self, obj):
        """Anzahl der Benutzer mit dieser Rolle als Badge"""
        count = obj.users.count()
        
        if count == 0:
            return format_html(
                '<span style="color: #9AA0A6; font-style: italic;">0 Benutzer</span>'
            )
        
        if count < 5:
            color = "#34A853"
        elif count < 20:
            color = "#1A73E8"
        else:
            color = "#FBBC05"
        
        return format_html(
            '<span class="status-badge" style="background-color: {}; color: white;">👥 {} Benutzer</span>',
            color, count
        )
    user_count_badge.short_description = "Zugewiesen"


# ============================================================================
# User Admin (Enhanced)
# ============================================================================
@admin.register(User, site=praxi_admin_site)
class UserAdmin(DjangoUserAdmin):
    """Admin-Klasse für Benutzer mit Premium-Badges"""
    
    list_display = (
        "username",
        "full_name_display",
        "email",
        "role_badge",
        "status_badge",
        "last_login_display",
    )
    list_filter = ("role", "is_staff", "is_active", "is_superuser")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)
    list_per_page = 50
    
    fieldsets = (
        ("🔐 Authentifizierung", {
            "fields": ("username", "password")
        }),
        ("👤 Persönliche Daten", {
            "fields": ("first_name", "last_name", "email", "role")
        }),
        ("🛡️ Berechtigungen", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
            "classes": ("collapse",)
        }),
        ("📅 Zeitstempel", {
            "fields": ("last_login", "date_joined"),
            "classes": ("collapse",)
        }),
    )
    
    add_fieldsets = (
        ("✨ Neuen Benutzer anlegen", {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2", "email", "role", "first_name", "last_name"),
        }),
    )
    
    readonly_fields = ("last_login", "date_joined")

    def lookup_allowed(self, lookup, value, request=None):
        """Allow a small set of safe related-field lookups used by dashboard links.

        Django admin rejects arbitrary querystring filters for security reasons.
        The PraxiApp UI links to user lists like:
        - /praxiadmin/core/user/?role__name=doctor
		
        So we explicitly allow filtering by role name.
        """
        if lookup == "role__name" or lookup.startswith("role__name__"):
            return True
        return super().lookup_allowed(lookup, value, request=request)

    def full_name_display(self, obj):
        """Vollständiger Name formatiert"""
        full_name = obj.get_full_name()
        if full_name.strip():
            return format_html('<strong style="color: #1A73E8; font-size: 14px;">{}</strong>', full_name)
        return mark_safe('<span style="color: #9AA0A6; font-style: italic;">Kein Name</span>')
    full_name_display.short_description = "Name"

    def role_badge(self, obj):
        """Rolle als farbiges Badge"""
        if not obj.role:
            return mark_safe('<span class="status-badge status-neutral">❓ Keine Rolle</span>')
        
        role_map = {
            "Admin": ("🔑", "#EA4335"),
            "Arzt": ("👨‍⚕️", "#1A73E8"),
            "Pflege": ("🩺", "#34A853"),
            "Empfang": ("📞", "#FBBC05"),
            "Management": ("📊", "#9334E6"),
        }
        
        role_name = obj.role.name
        icon, color = role_map.get(role_name, ("👤", "#5F6368"))
        
        return format_html(
            '<span class="status-badge" style="background-color: {}; color: white;">{} {}</span>',
            color, icon, role_name
        )
    role_badge.short_description = "Rolle"

    def status_badge(self, obj):
        """Benutzer-Status als Badge"""
        if obj.is_superuser:
            return mark_safe('<span class="status-badge" style="background-color: #9334E6; color: white;">👑 Superuser</span>')
        elif not obj.is_active:
            return mark_safe('<span class="status-badge status-critical">🚫 Inaktiv</span>')
        elif obj.is_staff:
            return mark_safe('<span class="status-badge status-success">✅ Staff</span>')
        else:
            return mark_safe('<span class="status-badge status-info">👤 Aktiv</span>')
    status_badge.short_description = "Status"

    def last_login_display(self, obj):
        """Letzter Login mit relativer Zeitangabe"""
        if not obj.last_login:
            return mark_safe('<span style="color: #9AA0A6; font-style: italic;">Noch nie</span>')
        
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.last_login
        
        if diff < timedelta(hours=1):
            color, text = "#34A853", "🟢 Gerade eben"
        elif diff < timedelta(hours=24):
            hours = diff.seconds // 3600
            color, text = "#1A73E8", f"🔵 Vor {hours}h"
        elif diff < timedelta(days=7):
            color, text = "#FBBC05", f"🟡 Vor {diff.days} Tag(en)"
        elif diff < timedelta(days=30):
            color, text = "#EA4335", f"🔴 Vor {diff.days} Tagen"
        else:
            color = "#9AA0A6"
            text = obj.last_login.strftime("⚪ %d.%m.%Y")
        
        return format_html('<span style="color: {}; font-weight: 500; font-size: 13px;">{}</span>', color, text)
    last_login_display.short_description = "Letzter Login"


# ============================================================================
# AuditLog Admin
# ============================================================================
@admin.register(AuditLog, site=praxi_admin_site)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin für Audit-Logs (Read-Only)"""
    
    list_display = (
        "id",
        "timestamp_display",
        "user_display",
        "role_badge",
        "action_badge",
        "patient_id_display",
    )
    list_filter = ("action", "role_name", "timestamp")
    search_fields = ("user__username", "action", "patient_id")
    ordering = ("-timestamp", "-id")
    list_per_page = 100
    date_hierarchy = "timestamp"
    
    readonly_fields = (
        "id",
        "user",
        "role_name",
        "action",
        "patient_id",
        "timestamp",
        "meta",
    )
    
    fieldsets = (
        ("📋 Audit-Eintrag", {
            "fields": ("id", "timestamp", "user", "role_name")
        }),
        ("🔍 Aktion", {
            "fields": ("action", "patient_id")
        }),
        ("📊 Metadaten", {
            "fields": ("meta",),
            "classes": ("collapse",)
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def timestamp_display(self, obj):
        """Timestamp formatiert"""
        return format_html(
            '<span style="color: #5F6368; font-family: monospace;">{}</span>',
            obj.timestamp.strftime("%d.%m.%Y %H:%M:%S")
        )
    timestamp_display.short_description = "Zeitstempel"

    def user_display(self, obj):
        """Benutzer mit Link"""
        if obj.user:
            return format_html(
                '<a href="/praxiadmin/core/user/{}/change/" style="color: #1A73E8;">{}</a>',
                obj.user.id, obj.user.username
            )
        return mark_safe('<span style="color: #9AA0A6; font-style: italic;">System</span>')
    user_display.short_description = "Benutzer"

    def role_badge(self, obj):
        """Rolle als Badge"""
        role_colors = {
            "admin": "#EA4335",
            "doctor": "#1A73E8",
            "assistant": "#34A853",
            "billing": "#FBBC05",
            "nurse": "#9334E6",
        }
        color = role_colors.get(obj.role_name, "#5F6368")
        return format_html(
            '<span class="status-badge" style="background-color: {}; color: white;">{}</span>',
            color, obj.role_name
        )
    role_badge.short_description = "Rolle"

    def action_badge(self, obj):
        """Aktion als Badge mit Icons"""
        action_map = {
            "appointment_create": ("📅", "#34A853", "Termin erstellt"),
            "appointment_update": ("✏️", "#1A73E8", "Termin geändert"),
            "appointment_delete": ("🗑️", "#EA4335", "Termin gelöscht"),
            "appointment_list": ("📋", "#5F6368", "Termine angezeigt"),
            "operation_create": ("🏥", "#34A853", "OP erstellt"),
            "operation_update": ("✏️", "#1A73E8", "OP geändert"),
            "operation_delete": ("🗑️", "#EA4335", "OP gelöscht"),
            "operation_list": ("📋", "#5F6368", "OPs angezeigt"),
            "patient_view": ("👁️", "#1A73E8", "Patient angesehen"),
        }
        icon, color, label = action_map.get(
            obj.action,
            ("❓", "#5F6368", obj.action)
        )
        return format_html(
            '<span class="status-badge" style="background-color: {}; color: white;">{} {}</span>',
            color, icon, label
        )
    action_badge.short_description = "Aktion"

    def patient_id_display(self, obj):
        """Patient-ID formatiert"""
        if obj.patient_id:
            return format_html(
                '<span style="font-family: monospace; color: #1A73E8;">#{}</span>',
                obj.patient_id
            )
        return mark_safe('<span style="color: #9AA0A6;">—</span>')
    patient_id_display.short_description = "Patient"
