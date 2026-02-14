from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.db import connection


def run_env_doctor() -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    database_url = os.getenv("DATABASE_URL")
    settings_module = os.getenv("DJANGO_SETTINGS_MODULE")

    _record(
        checks,
        "DATABASE_URL_present",
        bool(database_url),
        "DATABASE_URL is set" if database_url else "DATABASE_URL is missing",
    )
    if not database_url:
        errors.append("DATABASE_URL is required")

    if database_url:
        parsed = urlparse(database_url)
        is_postgres_url = parsed.scheme in {"postgres", "postgresql"}
        _record(
            checks,
            "DATABASE_URL_postgres_scheme",
            is_postgres_url,
            f"DATABASE_URL scheme is '{parsed.scheme or 'unknown'}'",
        )
        if not is_postgres_url:
            errors.append("DATABASE_URL must use postgres/postgresql scheme")

    has_settings_module = bool(settings_module)
    _record(
        checks,
        "DJANGO_SETTINGS_MODULE_present",
        has_settings_module,
        "DJANGO_SETTINGS_MODULE is set"
        if has_settings_module
        else "DJANGO_SETTINGS_MODULE not set (manage.py default may apply)",
    )
    if not has_settings_module:
        warnings.append("DJANGO_SETTINGS_MODULE not set explicitly")

    engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
    is_postgres_engine = engine == "django.db.backends.postgresql"
    _record(
        checks,
        "django_database_engine_postgresql",
        is_postgres_engine,
        f"Django DB engine: {engine or 'unknown'}",
    )
    if not is_postgres_engine:
        errors.append("Django default database engine is not PostgreSQL")

    db_connection_ok = True
    db_message = "Database connectivity check passed"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # pragma: no cover
        db_connection_ok = False
        db_message = f"Database connectivity failed: {exc}"
        errors.append("Database connectivity check failed")

    _record(checks, "database_select_1", db_connection_ok, db_message)

    return {
        "status": "ok" if not errors else "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
    }


def format_human(payload: dict[str, Any]) -> str:
    lines = ["Env Doctor report", f"status={payload['status']}"]
    for check in payload["checks"]:
        icon = "OK" if check["ok"] else "FAIL"
        lines.append(f"[{icon}] {check['name']}: {check['message']}")
    if payload["warnings"]:
        lines.append("Warnings:")
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
    if payload["errors"]:
        lines.append("Errors:")
        for error in payload["errors"]:
            lines.append(f"- {error}")
    return "\n".join(lines)


def _record(checks: list[dict[str, Any]], name: str, ok: bool, message: str) -> None:
    checks.append({"name": name, "ok": ok, "message": message})
