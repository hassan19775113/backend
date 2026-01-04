import logging

from .models import AuditLog

logger = logging.getLogger(__name__)


def log_patient_action(user, action, patient_id=None, meta=None):
    """Schreibt Patient-Access-Aktionen in die system-DB (alias: default)."""

    role_name = ''
    try:
        role = getattr(user, 'role', None)
        if role is not None:
            role_name = getattr(role, 'name', '') or ''
    except Exception:
        role_name = ''

    try:
        AuditLog.objects.using('default').create(
            user=user if getattr(user, 'is_authenticated', False) else None,
            role_name=role_name,
            action=action,
            patient_id=patient_id,
            meta=meta,
        )
    except Exception:
        logger.exception('AuditLog write failed (action=%s, patient_id=%s)', action, patient_id)
