#!/usr/bin/env python3
"""
Vercel Deployment Readiness Check
Überprüft ob das Projekt bereit für Vercel Deployment ist
"""

import os
import sys
from pathlib import Path

# Farben für Terminal-Ausgabe
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def check_file_exists(filepath: Path, description: str) -> bool:
    """Überprüft ob eine Datei existiert"""
    if filepath.exists():
        print(f"{GREEN}✓{RESET} {description}: {filepath.name}")
        return True
    else:
        print(f"{RED}✗{RESET} {description}: {filepath.name} FEHLT!")
        return False


def check_file_content(filepath: Path, search_text: str, description: str) -> bool:
    """Überprüft ob eine Datei bestimmten Text enthält"""
    try:
        content = filepath.read_text(encoding="utf-8")
        if search_text in content:
            print(f"{GREEN}✓{RESET} {description}")
            return True
        else:
            print(f"{YELLOW}⚠{RESET} {description} - Text nicht gefunden")
            return False
    except Exception as e:
        print(f"{RED}✗{RESET} {description} - Fehler: {e}")
        return False


def main():
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}VERCEL DEPLOYMENT READINESS CHECK{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

    # Root-Verzeichnis finden
    root_dir = Path(__file__).parent
    backend_dir = root_dir / "backend"

    all_checks_passed = True

    # 1. Erforderliche Dateien prüfen
    print(f"\n{BLUE}1. Erforderliche Konfigurationsdateien:{RESET}")
    checks = [
        (root_dir / "vercel.json", "Vercel-Konfiguration"),
        (root_dir / "requirements.txt", "Python-Dependencies"),
        (root_dir / ".vercelignore", "Vercel-Ignore-Datei"),
        (root_dir / ".env.example", "Environment-Template"),
        (root_dir / "build_files.sh", "Build-Script"),
    ]

    for filepath, desc in checks:
        if not check_file_exists(filepath, desc):
            all_checks_passed = False

    # 2. WSGI-Datei prüfen
    print(f"\n{BLUE}2. WSGI-Konfiguration:{RESET}")
    wsgi_file = backend_dir / "praxi_backend" / "wsgi.py"
    if check_file_exists(wsgi_file, "WSGI-Datei"):
        if not check_file_content(wsgi_file, "app = application", "Vercel Handler (app = application)"):
            all_checks_passed = False
    else:
        all_checks_passed = False

    # 3. Requirements prüfen
    print(f"\n{BLUE}3. Python-Dependencies:{RESET}")
    req_file = root_dir / "requirements.txt"
    if req_file.exists():
        required_packages = [
            ("Django", "Django Framework"),
            ("djangorestframework", "Django REST Framework"),
            ("psycopg", "PostgreSQL Driver"),
            ("whitenoise", "Static Files Handler"),
        ]
        for package, desc in required_packages:
            check_file_content(req_file, package, f"{desc} ({package})")

    # 4. Settings prüfen
    print(f"\n{BLUE}4. Django Settings:{RESET}")
    prod_settings = backend_dir / "praxi_backend" / "settings" / "prod.py"
    if check_file_exists(prod_settings, "Production Settings"):
        settings_checks = [
            ("SECURE_SSL_REDIRECT", "SSL Redirect aktiviert"),
            ("SECURE_PROXY_SSL_HEADER", "Proxy SSL Header konfiguriert"),
            ("STATICFILES_STORAGE", "Static Files Storage konfiguriert"),
        ]
        for check_text, desc in settings_checks:
            check_file_content(prod_settings, check_text, desc)

    # 5. Vercel.json prüfen
    print(f"\n{BLUE}5. Vercel-Konfiguration:{RESET}")
    vercel_json = root_dir / "vercel.json"
    if vercel_json.exists():
        vercel_checks = [
            ("@vercel/python", "Python Runtime konfiguriert"),
            ("python3.12", "Python Version 3.12"),
            ("praxi_backend.wsgi", "WSGI-Pfad konfiguriert"),
            ("praxi_backend.settings.prod", "Production Settings"),
        ]
        for check_text, desc in vercel_checks:
            check_file_content(vercel_json, check_text, desc)

    # Zusammenfassung
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    if all_checks_passed:
        print(f"{GREEN}✓ ALLE CHECKS BESTANDEN!{RESET}")
        print(f"\n{GREEN}Ihr Projekt ist bereit für Vercel Deployment!{RESET}")
        print(f"\n{BLUE}Nächste Schritte:{RESET}")
        print("1. Generieren Sie einen Secret Key: python generate_secret_key.py")
        print("2. Committen und pushen Sie Ihre Änderungen")
        print("3. Deployen Sie zu Vercel: vercel --prod")
        print("4. Setzen Sie Umgebungsvariablen im Vercel Dashboard")
        print("5. Führen Sie Datenbank-Migrationen aus")
        print(f"\n{BLUE}Siehe VERCEL_CHECKLIST.md für Details{RESET}")
    else:
        print(f"{YELLOW}⚠ EINIGE CHECKS FEHLGESCHLAGEN{RESET}")
        print(f"\n{YELLOW}Bitte beheben Sie die oben genannten Probleme vor dem Deployment{RESET}")
        sys.exit(1)

    print(f"{BLUE}{'=' * 70}{RESET}\n")


if __name__ == "__main__":
    main()
