# PraxiApp Backend - Vercel Deployment Guide

## 🚀 Deployment zu Vercel

Diese Anleitung führt Sie durch den Deployment-Prozess Ihrer Django-Anwendung auf Vercel.

## 📋 Voraussetzungen

1. **Vercel Account**: Erstellen Sie einen kostenlosen Account auf [vercel.com](https://vercel.com)
2. **Vercel CLI** (optional): `npm install -g vercel`
3. **PostgreSQL Datenbank**: Vercel Postgres oder externe PostgreSQL-Datenbank

## 🔧 Projekt-Setup

### 1. Repository vorbereiten

Stellen Sie sicher, dass alle notwendigen Dateien committet sind:
- `vercel.json` - Vercel-Konfiguration
- `build_files.sh` - Build-Script
- `requirements.txt` - Python-Dependencies
- `.vercelignore` - Ausgeschlossene Dateien
- `.env.example` - Umgebungsvariablen-Template

### 2. Datenbank einrichten

#### Option A: Vercel Postgres verwenden
1. Gehen Sie zu Ihrem Vercel Dashboard
2. Erstellen Sie eine neue PostgreSQL-Datenbank
3. Notieren Sie sich die Verbindungsdaten

#### Option B: Externe PostgreSQL-Datenbank
1. Verwenden Sie einen Anbieter wie Railway, Supabase, oder Neon
2. Erstellen Sie eine PostgreSQL-Datenbank
3. Notieren Sie sich die Verbindungsdaten

### 3. Umgebungsvariablen konfigurieren

In Ihrem Vercel-Projekt (Settings → Environment Variables) fügen Sie folgende Variablen hinzu:

**Erforderlich:**
```
DJANGO_SECRET_KEY=<generieren-sie-einen-sicheren-key>
DJANGO_SETTINGS_MODULE=praxi_backend.settings.prod
DJANGO_ALLOWED_HOSTS=.vercel.app,ihr-domain.com
DATABASE_URL=postgresql://user:password@host:port/dbname
```

**Optional aber empfohlen:**
```
DJANGO_DEBUG=False
CORS_ALLOWED_ORIGINS=https://ihr-frontend.vercel.app
SECURE_HSTS_SECONDS=31536000
```

#### Secret Key generieren:
```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 📦 Deployment-Schritte

### Methode 1: Über Vercel Dashboard (empfohlen)

1. **Gehen Sie zu [vercel.com](https://vercel.com)**
2. **Klicken Sie auf "Add New..." → "Project"**
3. **Importieren Sie Ihr Git Repository** (GitHub, GitLab, oder Bitbucket)
4. **Konfigurieren Sie das Projekt:**
   - Framework Preset: `Other`
   - Root Directory: `./` (Repository-Wurzel)
   - Build Command: `bash build_files.sh`
   - Output Directory: `backend/staticfiles`
5. **Fügen Sie Umgebungsvariablen hinzu** (siehe oben)
6. **Klicken Sie auf "Deploy"**

### Methode 2: Über Vercel CLI

```bash
# Vercel CLI installieren (falls nicht installiert)
npm install -g vercel

# In Ihr Projekt-Verzeichnis wechseln
cd /path/to/backend-1

# Login bei Vercel
vercel login

# Projekt deployen
vercel --prod

# Umgebungsvariablen setzen
vercel env add DJANGO_SECRET_KEY
vercel env add DATABASE_URL
# ... weitere Variablen
```

## 🗄️ Datenbank-Migration

Nach dem ersten Deployment müssen Sie die Datenbank-Migrationen ausführen:

### Option 1: Lokal ausführen (mit Vercel Postgres Connection)

```bash
# .env-Datei mit Production-Variablen erstellen
# Führen Sie Migrationen aus
cd backend
python manage.py migrate --settings=praxi_backend.settings.prod
python manage.py createsuperuser --settings=praxi_backend.settings.prod
```

### Option 2: Über Vercel Functions

Erstellen Sie eine temporäre API-Route für Migrationen (nur für Setup verwenden, dann entfernen!):

```python
# backend/praxi_backend/views.py
from django.http import JsonResponse
from django.core.management import call_command

def run_migrations(request):
    if request.GET.get('secret') == 'IHR_GEHEIMER_KEY':
        call_command('migrate')
        return JsonResponse({'status': 'migrations completed'})
    return JsonResponse({'error': 'unauthorized'}, status=403)
```

Rufen Sie auf: `https://ihr-projekt.vercel.app/migrate?secret=IHR_GEHEIMER_KEY`

**⚠️ WICHTIG:** Entfernen Sie diese Route nach dem Setup!

## ✅ Nach dem Deployment

### 1. Testen Sie Ihre Anwendung

- API-Endpoints: `https://ihr-projekt.vercel.app/api/...`
- Admin-Panel: `https://ihr-projekt.vercel.app/admin/`
- Health-Check: Erstellen Sie einen `/health/` Endpoint

### 2. Domain konfigurieren (optional)

1. Gehen Sie zu Projekt Settings → Domains
2. Fügen Sie Ihre Custom Domain hinzu
3. Aktualisieren Sie `DJANGO_ALLOWED_HOSTS` um Ihre Domain

### 3. SSL/HTTPS

Vercel aktiviert automatisch HTTPS für alle Deployments.

## 🔍 Troubleshooting

### Problem: "Application Error"

**Lösung:**
- Überprüfen Sie die Vercel Logs: Dashboard → Ihr Projekt → Deployments → Logs
- Stellen Sie sicher, dass alle Umgebungsvariablen gesetzt sind
- Überprüfen Sie `DJANGO_ALLOWED_HOSTS`

### Problem: Static Files werden nicht geladen

**Lösung:**
- Stellen Sie sicher, dass `python manage.py collectstatic` im Build läuft
- Überprüfen Sie `vercel.json` Routes-Konfiguration
- Überprüfen Sie WhiteNoise-Konfiguration in den Settings

### Problem: Datenbank-Verbindung schlägt fehl

**Lösung:**
- Überprüfen Sie `DATABASE_URL` Format
- Stellen Sie sicher, dass die Datenbank von außen erreichbar ist
- Überprüfen Sie Firewall-Regeln bei externen Datenbanken

### Problem: Import-Fehler

**Lösung:**
- Stellen Sie sicher, dass alle Dependencies in `requirements.txt` sind
- Überprüfen Sie Python-Version in `vercel.json` (python3.12)

## 📊 Monitoring & Logs

- **Logs ansehen:** Vercel Dashboard → Ihr Projekt → Deployments → Function Logs
- **Performance:** Vercel Analytics aktivieren
- **Errors:** Integrieren Sie ein Error-Tracking-Tool (z.B. Sentry)

## ⚠️ Wichtige Hinweise

1. **Serverless Limitations:**
   - Jede Function hat ein 10s Timeout (Hobby Plan) / 60s (Pro Plan)
   - Keine persistenten Prozesse (kein Celery direkt möglich)
   - Cold Starts können auftreten

2. **Alternativen für Background Tasks:**
   - Vercel Cron Jobs für geplante Tasks
   - Externe Worker-Services (z.B. Railway, Render)
   - Serverless Functions für einzelne Tasks

3. **Kosten:**
   - Hobby Plan: Kostenlos mit Limits
   - Pro Plan: Ab $20/Monat
   - Überprüfen Sie Vercel Pricing für Details

## 🔐 Sicherheit

- Verwenden Sie immer einen starken `DJANGO_SECRET_KEY`
- Setzen Sie `DJANGO_DEBUG=False` in Production
- Konfigurieren Sie CORS richtig
- Verwenden Sie Umgebungsvariablen für sensible Daten
- Aktivieren Sie HSTS und andere Security Headers

## 📚 Weitere Ressourcen

- [Vercel Dokumentation](https://vercel.com/docs)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)
- [Vercel Python Runtime](https://vercel.com/docs/functions/runtimes/python)

## 🆘 Support

Bei Problemen:
1. Überprüfen Sie die Vercel Logs
2. Konsultieren Sie die Vercel-Dokumentation
3. Prüfen Sie Django-Settings für Production
4. Erstellen Sie ein Issue im Repository

---

**Viel Erfolg mit Ihrem Deployment! 🎉**
