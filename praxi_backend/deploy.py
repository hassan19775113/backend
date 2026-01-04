import os
import subprocess
import sys
from dotenv import load_dotenv
import psycopg
import socket

print("\n🚀 Starte One‑Click‑Deployment...\n")

# ---------------------------------------------------------
# 1. .env laden
# ---------------------------------------------------------
print("📌 Schritt 1: Lade .env...")

if not os.path.exists(".env"):
    print("❌ .env fehlt! Deployment abgebrochen.")
    sys.exit(1)

load_dotenv()
print("✅ .env geladen")

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
    print("❌ PostgreSQL Verbindung fehlgeschlagen:")
    print(e)
    sys.exit(1)

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
    sys.exit(1)

sock.close()

# ---------------------------------------------------------
# 4. Dependencies installieren
# ---------------------------------------------------------
print("\n📌 Schritt 4: Installiere Dependencies...")

if not os.path.exists("requirements.txt"):
    print("❌ requirements.txt fehlt!")
    sys.exit(1)

subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

print("✅ Dependencies installiert")

# ---------------------------------------------------------
# 5. Migrationen ausführen
# ---------------------------------------------------------
print("\n📌 Schritt 5: Führe Migrationen aus...")

try:
    subprocess.run([sys.executable, "manage.py", "migrate"], check=True)
    print("✅ Migrationen erfolgreich")
except Exception as e:
    print("❌ Migrationen fehlgeschlagen:")
    print(e)
    sys.exit(1)

# ---------------------------------------------------------
# 6. Static Files sammeln
# ---------------------------------------------------------
print("\n📌 Schritt 6: Sammle Static Files...")

try:
    subprocess.run([sys.executable, "manage.py", "collectstatic", "--noinput"], check=True)
    print("✅ Static Files gesammelt")
except Exception as e:
    print("⚠️ collectstatic fehlgeschlagen (nicht kritisch):")
    print(e)

# ---------------------------------------------------------
# 7. Server starten
# ---------------------------------------------------------
print("\n📌 Schritt 7: Starte Django Server...")

try:
    subprocess.run([sys.executable, "manage.py", "runserver"])
except KeyboardInterrupt:
    print("\n🛑 Server manuell gestoppt.")
except Exception as e:
    print("❌ Fehler beim Starten des Servers:")
    print(e)

print("\n🎉 Deployment abgeschlossen!\n")