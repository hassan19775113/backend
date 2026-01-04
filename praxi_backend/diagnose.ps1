Write-Host "🔧 Starte KI-Diagnose..."

# venv aktivieren
Write-Host "📌 Aktiviere virtuelles Environment..."
.\.venv\Scripts\Activate.ps1

# diagnose.py ausführen
Write-Host "📌 Führe diagnose.py aus..."
python diagnose.py

Write-Host "✅ Diagnose abgeschlossen."