# PraxiApp Server Status

## ✅ Server läuft

**Status:** Development Server aktiv  
**URL:** http://localhost:8000  
**Zeit:** $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

### Verfügbare Endpoints:

#### Dashboard & UI:
- 🏠 **Haupt-Dashboard:** http://localhost:8000/praxi_backend/dashboard/
- 👥 **Patientenliste:** http://localhost:8000/praxi_backend/dashboard/patients/
- 📅 **Terminplanung:** http://localhost:8000/praxi_backend/dashboard/appointments/
- 👨‍⚕️ **Ärzte:** http://localhost:8000/praxi_backend/dashboard/doctors/
- 🏥 **Operationen:** http://localhost:8000/praxi_backend/dashboard/operations/
- 📊 **Scheduling:** http://localhost:8000/praxi_backend/dashboard/scheduling/
- 📦 **Ressourcen:** http://localhost:8000/praxi_backend/dashboard/resources/

#### API:
- 🔌 **API Root:** http://localhost:8000/api/
- 📅 **Appointments API:** http://localhost:8000/api/appointments/
- 👥 **Patients API:** http://localhost:8000/api/patients/
- 👨‍⚕️ **Doctors API:** http://localhost:8000/api/doctors/

#### Admin:
- ⚙️ **Django Admin:** http://localhost:8000/admin/

### Server stoppen:

```powershell
# Prozess beenden (falls im Hintergrund)
Get-Process python | Where-Object {$_.Path -like "*\.venv*"} | Stop-Process
```

### Logs anzeigen:

Der Server läuft im Hintergrund. Logs werden in der Konsole ausgegeben, wo der Server gestartet wurde.

### Nächste Schritte:

1. Öffne http://localhost:8000/praxi_backend/dashboard/ im Browser
2. Teste die verschiedenen Masken und Funktionen
3. Prüfe die Browser-Konsole auf JavaScript-Fehler
4. Teste die API-Endpoints

---

**Hinweis:** Der Server läuft im Development-Modus mit PostgreSQL (Single-DB: `default`).

