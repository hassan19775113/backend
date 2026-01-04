#!/usr/bin/env python
"""
PraxiApp Deployment Check Script
================================
Validiert das Projekt für lokale Entwicklung und Produktion.

Verwendung:
    python scripts/deploy_check.py
    python scripts/deploy_check.py --settings=praxi_backend.settings
"""

import os
import sys
from pathlib import Path

# Projekt-Root zum Pfad hinzufügen
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def main():
    # Settings-Modul aus Argumenten oder Default
    settings_module = 'praxi_backend.settings_dev'
    for arg in sys.argv[1:]:
        if arg.startswith('--settings='):
            settings_module = arg.split('=')[1]
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)
    
    print("=" * 60)
    print(f"  PraxiApp Deployment Check")
    print(f"  Settings: {settings_module}")
    print("=" * 60)
    
    results = []
    
    # 1. Django Setup
    print("\n[1/8] Django Setup...")
    try:
        import django
        django.setup()
        results.append(("Django Setup", "OK", f"v{django.VERSION[0]}.{django.VERSION[1]}"))
    except Exception as e:
        results.append(("Django Setup", "FAIL", str(e)))
        print(f"  FATAL: {e}")
        return 1
    
    from django.conf import settings
    from django.core.management import call_command
    from io import StringIO
    
    # 2. System Check
    print("[2/8] Django System Check...")
    out, err = StringIO(), StringIO()
    try:
        call_command('check', stdout=out, stderr=err)
        results.append(("System Check", "OK", "No issues"))
    except Exception as e:
        results.append(("System Check", "FAIL", str(e)))
    
    # 3. Datenbank-Verbindung
    print("[3/8] Database Connection...")
    try:
        from django.db import connections
        conn = connections['default']
        conn.ensure_connection()
        db_engine = settings.DATABASES['default']['ENGINE']
        db_name = settings.DATABASES['default'].get('NAME', 'unknown')
        results.append(("Database", "OK", f"{db_engine.split('.')[-1]}: {Path(db_name).name if 'sqlite' in db_engine else db_name}"))
    except Exception as e:
        results.append(("Database", "FAIL", str(e)))
    
    # 4. Migrations
    print("[4/8] Migrations Status...")
    try:
        from django.db.migrations.executor import MigrationExecutor
        executor = MigrationExecutor(connections['default'])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            results.append(("Migrations", "WARN", f"{len(plan)} pending"))
        else:
            results.append(("Migrations", "OK", "All applied"))
    except Exception as e:
        results.append(("Migrations", "FAIL", str(e)))
    
    # 5. INSTALLED_APPS
    print("[5/8] Installed Apps...")
    required_apps = ['praxi_backend.core', 'praxi_backend.appointments', 'praxi_backend.medical', 'praxi_backend.patients']
    missing = [app for app in required_apps if app not in settings.INSTALLED_APPS]
    if missing:
        results.append(("Installed Apps", "FAIL", f"Missing: {missing}"))
    else:
        results.append(("Installed Apps", "OK", f"{len(required_apps)} PraxiApp modules"))
    
    # 6. Static Files
    print("[6/8] Static Files...")
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if static_root and Path(static_root).exists():
        results.append(("Static Files", "OK", f"STATIC_ROOT exists"))
    elif static_root:
        results.append(("Static Files", "WARN", "STATIC_ROOT not collected yet"))
    else:
        results.append(("Static Files", "FAIL", "STATIC_ROOT not set"))
    
    # 7. Security Settings (nur Prod)
    print("[7/8] Security Settings...")
    if 'settings_dev' in settings_module:
        results.append(("Security", "SKIP", "DEV mode"))
    else:
        issues = []
        if settings.DEBUG:
            issues.append("DEBUG=True")
        if '*' in getattr(settings, 'ALLOWED_HOSTS', []):
            issues.append("ALLOWED_HOSTS contains *")
        if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
            issues.append("SECURE_SSL_REDIRECT=False")
        if issues:
            results.append(("Security", "WARN", "; ".join(issues)))
        else:
            results.append(("Security", "OK", "Production ready"))
    
    # 8. Dependencies
    print("[8/8] Dependencies...")
    try:
        import rest_framework
        import corsheaders
        import rest_framework_simplejwt
        results.append(("Dependencies", "OK", "Core packages installed"))
    except ImportError as e:
        results.append(("Dependencies", "FAIL", str(e)))
    
    # Zusammenfassung
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    
    for name, status, detail in results:
        icon = {"OK": "[OK]", "WARN": "[!!]", "FAIL": "[XX]", "SKIP": "[--]"}.get(status, "[??]")
        print(f"  {icon} {name:<20} {detail}")
    
    fails = sum(1 for _, s, _ in results if s == "FAIL")
    warns = sum(1 for _, s, _ in results if s == "WARN")
    
    print("\n" + "-" * 60)
    if fails > 0:
        print(f"  RESULT: {fails} FAILURES, {warns} WARNINGS")
        return 1
    elif warns > 0:
        print(f"  RESULT: PASSED with {warns} WARNINGS")
        return 0
    else:
        print("  RESULT: ALL CHECKS PASSED")
        return 0


if __name__ == '__main__':
    sys.exit(main())
