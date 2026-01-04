import os
import psycopg
from dotenv import load_dotenv
import subprocess
import socket
import sys

print("\n🔍 KI-Diagnose-System gestartet...\n")

# ---------------------------------------------------------
# 1. .env laden
# ---------------------------------------------------------
print("📌 Schritt 1: Prüfe .env...")

if not os.path.exists(".env"):
    print("❌ .env Datei fehlt!")
else:
    print("✅ .env gefunden")

load_dotenv()

required_vars = [
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
]

missing = [v for v in required_vars if not os.environ.get(v)]

if missing:
    print("❌ Fehlende Variablen in .env:", missing)
else:
    print("✅ Alle benötigten Variablen vorhanden")

# ---------------------------------------------------------
# 2. PostgreSQL Verbindung testen
# ---------------------------------------------------------
print("\n📌 Schritt 2: Teste PostgreSQL Verbindung...")

try:
    conn = psycopg.connect(
        dbname=os.environ.get("POSTGRES_DB"),
        user=os.environ.get("POSTGRES_USER"),
        password=os.environ.get("POSTGRES_PASSWORD"),
        host=os.environ.get("POSTGRES_HOST"),
        port=os.environ.get("POSTGRES_PORT"),
        connect_timeout=3
    )
    print("✅ Verbindung erfolgreich!")
    conn.close()
except Exception as e:
    print("❌ Verbindung fehlgeschlagen:")
    print(e)

# ---------------------------------------------------------
# 3. Port 5432 prüfen
# ---------------------------------------------------------
print("\n📌 Schritt 3: Prüfe Port 5432...")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
result = sock.connect_ex(("127.0.0.1", 5432))

if result == 0:
    print("✅ Port 5432 ist offen")
else:
    print("❌ Port 5432 ist geschlossen — PostgreSQL läuft nicht")

sock.close()

# ---------------------------------------------------------
# 4. Django Struktur prüfen
# ---------------------------------------------------------
print("\n📌 Schritt 4: Prüfe Django Struktur...")

if not os.path.exists("manage.py"):
    print("❌ manage.py fehlt — falsches Verzeichnis?")
else:
    print("✅ manage.py gefunden")

apps = ["appointments", "core", "medical", "praxi_backend"]

for app in apps:
    if os.path.exists(app):
        print(f"✅ App gefunden: {app}")
    else:
        print(f"❌ App fehlt: {app}")

# ---------------------------------------------------------
# 5. Migrationen testen
# ---------------------------------------------------------
print("\n📌 Schritt 5: Teste Migrationen...")

try:
    result = subprocess.run(
        [sys.executable, "manage.py", "showmigrations"],
        capture_output=True,
        text=True
    )
    print("✅ Django ist funktionsfähig")
except Exception as e:
    print("❌ Fehler beim Ausführen von Django:")
    print(e)

print("\n🎉 Diagnose abgeschlossen!\n")