#!/bin/bash
# ==============================================================================
# PraxiApp Deployment Script
# ==============================================================================
# Verwendung: ./deploy.sh [dev|prod]
# ==============================================================================

set -e

MODE=${1:-dev}
echo "========================================"
echo "  PraxiApp Deployment: $MODE"
echo "========================================"

# Verzeichnis wechseln
cd "$(dirname "$0")"

# Virtual Environment aktivieren
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "ERROR: Virtual environment nicht gefunden!"
    exit 1
fi

# Dependencies installieren
echo "[1/6] Dependencies installieren..."
pip install -r praxi_backend/requirements.txt --quiet

if [ "$MODE" = "prod" ]; then
    export DJANGO_SETTINGS_MODULE=praxi_backend.settings_prod
    
    echo "[2/6] Migrations prüfen..."
    python manage.py migrate --database=default --check
    
    echo "[3/6] Static Files sammeln..."
    python manage.py collectstatic --noinput
    
    echo "[4/6] System Check..."
    python manage.py check --deploy
    
    echo "[5/6] Logs-Verzeichnis erstellen..."
    mkdir -p logs
    
    echo "[6/6] Gunicorn starten..."
    exec gunicorn praxi_backend.wsgi:application \
        --bind ${GUNICORN_BIND:-0.0.0.0:8000} \
        --workers ${GUNICORN_WORKERS:-4} \
        --timeout 120 \
        --access-logfile logs/access.log \
        --error-logfile logs/error.log \
        --capture-output
else
    export DJANGO_SETTINGS_MODULE=praxi_backend.settings_dev
    
    echo "[2/6] Migrations anwenden..."
    python manage.py migrate --database=default
    
    echo "[3/6] Static Files prüfen..."
    # Keine collectstatic in Dev
    
    echo "[4/6] System Check..."
    python manage.py check
    
    echo "[5/6] Übersprungen (Prod only)..."
    
    echo "[6/6] Development Server starten..."
    exec python manage.py runserver 0.0.0.0:8000
fi
