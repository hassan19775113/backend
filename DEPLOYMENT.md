# PraxiApp Deployment Checklist

## 📋 Pre-Deployment Checklist

### 1. Environment Setup
- [ ] `.env` file created from `.env.example`
- [ ] All secrets generated (use `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`)
- [ ] Database credentials configured
- [ ] Redis connection verified
- [ ] ALLOWED_HOSTS set correctly

### 2. SSL/TLS Certificates
- [ ] SSL certificates obtained (Let's Encrypt or commercial)
- [ ] Certificates placed in `docker/ssl/` directory
- [ ] Nginx configured with certificate paths

### 3. Database Preparation
- [ ] PostgreSQL databases created:
  - `praxiapp_system` (managed by Django)
  - `praxiapp` (legacy medical, read-only)
- [ ] Database users created with appropriate permissions

---

## 🐳 Docker Deployment

### Development Environment
```bash
# Build and start
docker-compose -f docker-compose.dev.yml up --build -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f web

# Run migrations
docker-compose -f docker-compose.dev.yml exec web python manage.py migrate --database=default

# Create superuser
docker-compose -f docker-compose.dev.yml exec web python manage.py createsuperuser

# Stop
docker-compose -f docker-compose.dev.yml down
```

### Production Environment
```bash
# Build images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.prod.yml exec web python manage.py migrate --database=default

# Collect static files
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Create superuser
docker-compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop
docker-compose -f docker-compose.prod.yml down
```

---

## 🖥️ Bare-Metal Deployment (Systemd)

### 1. System Preparation
```bash
# Create application user
sudo useradd --system --shell /bin/false --create-home --home-dir /opt/praxiapp praxiapp

# Create directories
sudo mkdir -p /opt/praxiapp/backend
sudo mkdir -p /var/log/praxiapp
sudo chown -R praxiapp:praxiapp /opt/praxiapp /var/log/praxiapp
```

### 2. Deploy Application
```bash
# Clone/copy application
sudo -u praxiapp git clone <repo> /opt/praxiapp/backend

# Create virtual environment
cd /opt/praxiapp/backend
sudo -u praxiapp python3 -m venv /opt/praxiapp/venv

# Install dependencies
sudo -u praxiapp /opt/praxiapp/venv/bin/pip install -r praxi_backend/requirements.txt

# Copy and configure .env
sudo cp .env.example .env
sudo nano .env

# Run migrations
sudo -u praxiapp /opt/praxiapp/venv/bin/python manage.py migrate --database=default

# Collect static files
sudo -u praxiapp /opt/praxiapp/venv/bin/python manage.py collectstatic --noinput
```

### 3. Install Systemd Services
```bash
cd systemd
sudo ./install-services.sh

# Start services
sudo systemctl start praxiapp-gunicorn
sudo systemctl start praxiapp-celery
sudo systemctl start praxiapp-celerybeat

# Check status
sudo systemctl status praxiapp-gunicorn
```

---

## ✅ Post-Deployment Verification

### 1. Health Checks
```bash
# API health
curl -s http://localhost:8000/api/health/ | jq

# Admin panel
curl -I http://localhost:8000/admin/
```

### 2. Smoke Test
```bash
# Run smoke test script
python scripts/smoke_test.py --base-url https://your-domain.com
```

### 3. Log Verification
```bash
# Docker logs
docker-compose -f docker-compose.prod.yml logs web

# Systemd logs
journalctl -u praxiapp-gunicorn -f
tail -f /var/log/praxiapp/gunicorn-error.log
```

---

## 🔧 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `CSRF verification failed` | Check `CSRF_TRUSTED_ORIGINS` in settings |
| `Static files 404` | Run `collectstatic`, check Nginx config |
| `Database connection refused` | Verify `SYS_DB_*` variables and PostgreSQL status |
| `Redis connection error` | Check `REDIS_HOST` and Redis service status |
| `Permission denied` | Check file ownership (`chown praxiapp:praxiapp`) |

### Useful Commands
```bash
# Check Django settings
docker-compose exec web python -c "from django.conf import settings; print(settings.DATABASES)"

# Test database connection
docker-compose exec web python manage.py dbshell --database=default

# Check Celery workers
docker-compose exec web celery -A praxi_backend inspect active

# Force rebuild
docker-compose -f docker-compose.prod.yml build --no-cache
```

---

## 📊 Monitoring

### Recommended Tools
- **Logs**: ELK Stack, Loki + Grafana
- **Metrics**: Prometheus + Grafana
- **APM**: Sentry (already configured in settings_prod.py)
- **Uptime**: UptimeRobot, Pingdom

### Key Metrics to Monitor
- Response time (P50, P95, P99)
- Error rate (5xx responses)
- Database connection pool usage
- Celery queue length
- Memory/CPU usage per container

---

## 🔐 Security Checklist

- [ ] DEBUG = False
- [ ] SECRET_KEY unique and strong
- [ ] HTTPS enforced (SECURE_SSL_REDIRECT)
- [ ] HSTS enabled
- [ ] Database credentials not in version control
- [ ] Firewall configured (only 80, 443 exposed)
- [ ] Regular security updates scheduled
- [ ] Backup strategy implemented

---

## 📦 Backup Strategy

### Database Backup
```bash
# Manual backup
docker-compose exec db pg_dump -U postgres praxiapp_system > backup_$(date +%Y%m%d).sql

# Automated backup (add to crontab)
0 2 * * * docker-compose -f /opt/praxiapp/docker-compose.prod.yml exec -T db pg_dump -U postgres praxiapp_system | gzip > /opt/praxiapp/backups/backup_$(date +\%Y\%m\%d).sql.gz
```

### Restore
```bash
docker-compose exec -T db psql -U postgres praxiapp_system < backup_20240101.sql
```

---

*Last updated: 2024*
