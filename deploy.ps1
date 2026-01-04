# ==============================================================================
# PraxiApp Deployment Script (PowerShell)
# ==============================================================================
# Verwendung: .\deploy.ps1 [-Mode dev|prod]
# ==============================================================================

param(
    [ValidateSet("dev", "prod")]
    [string]$Mode = "dev",

    # If set, run deploy steps but do not start long-running server processes
    # (runserver in dev, gunicorn in prod). This is useful for CI or when you
    # want to start the server manually.
    [switch]$SkipServer
)

Write-Host "========================================"
Write-Host "  PraxiApp Deployment: $Mode"
Write-Host "========================================"

# Verzeichnis
Set-Location $PSScriptRoot

# Virtual Environment aktivieren
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & ".\.venv\Scripts\Activate.ps1"
} elseif (Test-Path ".\venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Error "Virtual environment nicht gefunden!"
    exit 1
}

# Dependencies
Write-Host "[1/6] Dependencies installieren..."
python -m pip install --progress-bar off -r praxi_backend\requirements.txt

if (-not $?) {
    Write-Error "Dependency-Installation fehlgeschlagen. Abbruch."
    exit 1
}

if ($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0) {
    Write-Error "Dependency-Installation fehlgeschlagen (ExitCode=$LASTEXITCODE). Abbruch."
    exit $LASTEXITCODE
}

if ($Mode -eq "prod") {
    $env:DJANGO_SETTINGS_MODULE = "praxi_backend.settings_prod"
    
    Write-Host "[2/6] Migrations prüfen..."
    python manage.py migrate --database=default --check
    
    Write-Host "[3/6] Static Files sammeln..."
    python manage.py collectstatic --noinput
    
    Write-Host "[4/6] System Check..."
    python manage.py check --deploy
    
    Write-Host "[5/6] Logs-Verzeichnis..."
    New-Item -ItemType Directory -Force -Path logs | Out-Null
    
    if ($SkipServer) {
        Write-Host "[6/6] Server-Start übersprungen (-SkipServer)"
        exit 0
    }

    Write-Host "[6/6] Gunicorn starten..."
    $workers = if ($env:GUNICORN_WORKERS) { [int]$env:GUNICORN_WORKERS } else { 4 }
    $bind = if ($env:GUNICORN_BIND) { $env:GUNICORN_BIND } else { "0.0.0.0:8000" }
    gunicorn praxi_backend.wsgi:application `
        --bind $bind `
        --workers $workers `
        --timeout 120
} else {
    $env:DJANGO_SETTINGS_MODULE = "praxi_backend.settings_dev"
    
    Write-Host "[2/6] Migrations anwenden..."
    python manage.py migrate --database=default
    
    Write-Host "[3/6] Übersprungen (Dev)..."
    Write-Host "[4/6] System Check..."
    python manage.py check
    
    Write-Host "[5/6] Übersprungen (Dev)..."
    
    if ($SkipServer) {
        Write-Host "[6/6] Server-Start übersprungen (-SkipServer)"
        exit 0
    }

    Write-Host "[6/6] Development Server starten..."
    python manage.py runserver 0.0.0.0:8000
}
