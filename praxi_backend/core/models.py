from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class Role(models.Model):
    """User roles for RBAC (Role-Based Access Control).

    Standard roles: admin, assistant, doctor, billing, nurse
    """

    name = models.CharField(max_length=64, unique=True, db_index=True)
    label = models.CharField(max_length=128)

    class Meta:
        db_table = 'core_role'
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self) -> str:
        return self.label


class User(AbstractUser):
    """Custom User model with role-based access control.

    Extends Django's AbstractUser with:
    - role: ForeignKey to Role for RBAC
    - calendar_color: Hex color for calendar display
    - email: Made unique (required for JWT auth)
    """

    email = models.EmailField('email address', blank=True, unique=True)
    calendar_color = models.CharField(max_length=7, blank=True, default='#1E90FF')
    role = models.ForeignKey(
        Role,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='users',
    )

    class Meta:
        db_table = 'core_user'
        ordering = ['username']
        verbose_name = 'User'
        verbose_name_plural = 'Users'


class AuditLog(models.Model):
    """Audit log for patient-related actions.

    Tracks who accessed/modified patient data and when.
    patient_id is stored as IntegerField (not FK) per dual-DB architecture.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    role_name = models.CharField(max_length=50, db_index=True)
    action = models.CharField(max_length=50, db_index=True)
    patient_id = models.IntegerField(null=True, blank=True, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    meta = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = 'core_auditlog'
        ordering = ['-timestamp', '-id']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['patient_id', 'timestamp']),
        ]

    def __str__(self) -> str:
        return f"{self.timestamp} {self.action} (patient_id={self.patient_id})"

