"""
Development Settings für PraxiApp Backend (Windows + SQLite).

Verwendung:
    $env:DJANGO_SETTINGS_MODULE = "praxi_backend.settings_dev"
    python manage.py runserver

Oder in manage.py: os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'praxi_backend.settings_dev')
"""

from .settings import *

# ---------------------------------------------------------
# DEVELOPMENT SETTINGS (WINDOWS + SQLITE)
# ---------------------------------------------------------

# Debug-Modus aktivieren
DEBUG = True

# Lokale Entwicklung: alle Hosts erlauben
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', '*']

# ---------------------------------------------------------
# DATABASES: SQLite für lokale Entwicklung
# ---------------------------------------------------------

DATABASES = {
    # System-DB (read/write) - SQLite für lokale Entwicklung
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'dev.sqlite3',
        'OPTIONS': {
            'timeout': 20,
        },
    },
    # Medical-DB (read-only) - SQLite für lokale Entwicklung
    # In DEV: Gleiche DB wie default, da keine echte Legacy-DB vorhanden
    'medical': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'dev.sqlite3',
        'OPTIONS': {
            'timeout': 20,
        },
    },
}

# Kein Multi-DB-Routing in DEV (alles läuft auf default)
DATABASE_ROUTERS = []

# ---------------------------------------------------------
# INSTALLED_APPS: Vollständige Liste aller Apps
# ---------------------------------------------------------

INSTALLED_APPS = [
    # Django-Standard-Apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-Party
    'rest_framework',
    'corsheaders',

    # PraxiApp-Module
    'praxi_backend.core',
    'praxi_backend.appointments',
    'praxi_backend.medical',
    'praxi_backend.patients',
    'praxi_backend.dashboard',
]

# ---------------------------------------------------------
# MIDDLEWARE: CORS für lokale Entwicklung hinzufügen
# ---------------------------------------------------------

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Muss vor CommonMiddleware stehen
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ---------------------------------------------------------
# AUTH: Custom User Model (aus praxi_backend.core)
# ---------------------------------------------------------

AUTH_USER_MODEL = 'core.User'

# ---------------------------------------------------------
# REST FRAMEWORK: Authentifizierung & Permissions
# ---------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # Für Browsable API
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',  # Für DEV
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.FormParser',
        'rest_framework.parsers.MultiPartParser',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
}

# ---------------------------------------------------------
# SIMPLE JWT: Token-Konfiguration
# ---------------------------------------------------------

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=2),  # Länger für DEV
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
}

# ---------------------------------------------------------
# CORS: Alle Origins für lokale Entwicklung erlauben
# ---------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = True  # Nur für DEV!
CORS_ALLOW_CREDENTIALS = True

# CSRF: Lokale Origins vertrauen
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]

# ---------------------------------------------------------
# STATIC & MEDIA: Lokale Entwicklung
# ---------------------------------------------------------

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'praxi_backend' / 'static',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ---------------------------------------------------------
# LOGGING: Ausführliches Logging für Entwicklung
# ---------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  # Auf DEBUG setzen für SQL-Queries
            'propagate': False,
        },
        'praxi_backend': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# ---------------------------------------------------------
# CELERY / REDIS: Deaktiviert für lokale Entwicklung
# ---------------------------------------------------------

CELERY_BROKER_URL = None
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = True  # Tasks synchron ausführen

# ---------------------------------------------------------
# SECURITY: Relaxed für lokale Entwicklung
# ---------------------------------------------------------

# Diese Settings sind nur für DEV - in Produktion müssen sie aktiviert sein!
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# ---------------------------------------------------------
# EMAIL: Console-Backend für Entwicklung
# ---------------------------------------------------------

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ---------------------------------------------------------
# CACHES: Lokaler Memory-Cache für Entwicklung
# ---------------------------------------------------------

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}