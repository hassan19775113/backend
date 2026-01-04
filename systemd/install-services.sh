#!/bin/bash
# ==============================================================================
# Systemd Services Installation Script
# ==============================================================================
# Run as root: sudo ./install-services.sh
# ==============================================================================

set -e

echo "=========================================="
echo "  PraxiApp Systemd Services Installation"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (sudo ./install-services.sh)"
    exit 1
fi

# Create praxiapp user if not exists
if ! id "praxiapp" &>/dev/null; then
    echo "[1/7] Creating praxiapp user..."
    useradd --system --shell /bin/false --create-home --home-dir /opt/praxiapp praxiapp
else
    echo "[1/7] User praxiapp already exists."
fi

# Create directories
echo "[2/7] Creating directories..."
mkdir -p /var/log/praxiapp
mkdir -p /run/gunicorn
mkdir -p /run/celery
chown praxiapp:praxiapp /var/log/praxiapp
chown praxiapp:praxiapp /run/gunicorn
chown praxiapp:praxiapp /run/celery

# Copy service files
echo "[3/7] Installing service files..."
cp gunicorn.service /etc/systemd/system/praxiapp-gunicorn.service
cp celery.service /etc/systemd/system/praxiapp-celery.service
cp celerybeat.service /etc/systemd/system/praxiapp-celerybeat.service

# Reload systemd
echo "[4/7] Reloading systemd daemon..."
systemctl daemon-reload

# Enable services
echo "[5/7] Enabling services..."
systemctl enable praxiapp-gunicorn.service
systemctl enable praxiapp-celery.service
systemctl enable praxiapp-celerybeat.service

echo "[6/7] Services installed successfully!"
echo ""
echo "Commands:"
echo "  Start:   sudo systemctl start praxiapp-gunicorn"
echo "  Stop:    sudo systemctl stop praxiapp-gunicorn"
echo "  Status:  sudo systemctl status praxiapp-gunicorn"
echo "  Logs:    sudo journalctl -u praxiapp-gunicorn -f"
echo ""
echo "[7/7] Done!"
