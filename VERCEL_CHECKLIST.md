# 🚀 Vercel Deployment - Schnellstart Checkliste

## ✅ Pre-Deployment Checkliste

### 1. Dateien überprüfen
- [ ] `vercel.json` existiert im Root-Verzeichnis
- [ ] `build_files.sh` existiert im Root-Verzeichnis
- [ ] `requirements.txt` im Root-Verzeichnis (Vercel-optimiert)
- [ ] `.vercelignore` existiert
- [ ] `.env.example` als Referenz vorhanden

### 2. Code vorbereiten
- [ ] Alle Änderungen committet und gepusht
- [ ] `backend/praxi_backend/wsgi.py` enthält `app = application` für Vercel
- [ ] Production Settings in `backend/praxi_backend/settings/prod.py` konfiguriert

### 3. Datenbank einrichten
- [ ] PostgreSQL-Datenbank erstellt (Vercel Postgres oder extern)
- [ ] Datenbank-Verbindungsstring notiert
- [ ] Datenbank erreichbar und getestet

### 4. Umgebungsvariablen vorbereiten
- [ ] `DJANGO_SECRET_KEY` generiert
- [ ] `DATABASE_URL` oder Postgres-Credentials
- [ ] `DJANGO_ALLOWED_HOSTS` mit Vercel-Domain
- [ ] `CORS_ALLOWED_ORIGINS` mit Frontend-URL

## 🔧 Deployment Schritte

### Schritt 1: Vercel-Projekt erstellen
```bash
# CLI-Methode
vercel login
vercel --prod

# ODER über Web-Dashboard
# https://vercel.com/new
```

### Schritt 2: Umgebungsvariablen setzen

Im Vercel Dashboard unter "Settings" → "Environment Variables":

**Minimal erforderlich:**
```
DJANGO_SECRET_KEY=<ihr-secret-key>
DJANGO_SETTINGS_MODULE=praxi_backend.settings.prod
DJANGO_ALLOWED_HOSTS=.vercel.app
DATABASE_URL=postgresql://user:pass@host:port/db
```

**Empfohlen:**
```
DJANGO_DEBUG=False
CORS_ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

### Schritt 3: Initial Deployment

1. Push zu Git Repository
2. Vercel deployed automatisch ODER
3. Manuell: `vercel --prod`

### Schritt 4: Datenbank-Migration

**Option A - Lokal mit Production DB:**
```bash
cd backend
export DATABASE_URL="postgresql://..."
export DJANGO_SETTINGS_MODULE=praxi_backend.settings.prod
python manage.py migrate
python manage.py createsuperuser
```

**Option B - Via Vercel CLI:**
```bash
vercel env pull .env.production
# Bearbeiten Sie .env.production mit lokalen Werten
python manage.py migrate --settings=praxi_backend.settings.prod
```

### Schritt 5: Testen

- [ ] API-Endpoint testen: `https://ihr-projekt.vercel.app/api/`
- [ ] Admin-Panel öffnen: `https://ihr-projekt.vercel.app/admin/`
- [ ] Frontend-Verbindung testen (falls vorhanden)
- [ ] Logs prüfen im Vercel Dashboard

## 🔍 Schnelle Problemlösung

| Problem | Lösung |
|---------|--------|
| "Application Error" | Logs prüfen, Umgebungsvariablen überprüfen |
| 500 Internal Server Error | `DJANGO_SECRET_KEY` und `DATABASE_URL` prüfen |
| Static Files fehlen | `build_files.sh` läuft? `collectstatic` erfolgreich? |
| CORS-Fehler | `CORS_ALLOWED_ORIGINS` korrekt gesetzt? |
| Database Connection Error | `DATABASE_URL` Format prüfen, Firewall-Regeln |

## 📝 Secret Key generieren

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 🔗 Wichtige Links

- Vercel Dashboard: https://vercel.com/dashboard
- Vercel Logs: Dashboard → Projekt → Deployments → Function Logs
- Vercel Docs: https://vercel.com/docs

## 🎯 Nach dem ersten Deployment

- [ ] Custom Domain hinzufügen (optional)
- [ ] Analytics aktivieren (optional)
- [ ] Error Tracking einrichten (z.B. Sentry)
- [ ] Backup-Strategie für Datenbank
- [ ] Monitoring einrichten
- [ ] CI/CD Pipeline testen

## ⚡ Quick Deploy Command

```bash
# Alles in einem Befehl
git add . && git commit -m "Ready for Vercel" && git push && vercel --prod
```

## 📞 Hilfe benötigt?

Siehe detaillierte Dokumentation in [VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md)
