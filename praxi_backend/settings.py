"""
Django settings for PraxiApp MVP backend.

Wichtig: Dieses Setup nutzt PostgreSQL und führt keine Migrationen automatisch aus.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from datetime import timedelta


BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-f((&w^a2svg9ajuahn!wf4s$xr1in)-1+jhi_4%5_2jc+-*=&$'
)

DEBUG = True  # Temporär auf True setzen für Development

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',')
    if host.strip()
]


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',

    # KORRIGIERT: Apps liegen unter praxi_backend/
    'praxi_backend.core',
    'praxi_backend.appointments',
    'praxi_backend.medical',
    'praxi_backend.patients',
    'praxi_backend.dashboard',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'praxi_backend.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Templates-Verzeichnis hinzugefügt
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


WSGI_APPLICATION = 'praxi_backend.wsgi.application'


DATABASES = {
    # Django-Systemdatenbank (Auth, Rollen, Admin, Sessions, zukünftig Audit-Logs)
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('SYS_DB_NAME', 'praxiapp_system'),
        'USER': os.getenv('SYS_DB_USER', 'postgres'),
        'PASSWORD': os.getenv('SYS_DB_PASSWORD') or os.getenv('PGPASSWORD', ''),
        'HOST': os.getenv('SYS_DB_HOST', 'localhost'),
        'PORT': os.getenv('SYS_DB_PORT', '5432'),
        'CONN_MAX_AGE': int(os.getenv('SYS_DB_CONN_MAX_AGE', '0')),
    },

    # Medizinische Bestands-DB (bleibt schema-seitig unverändert; später unmanaged Models)
    'medical': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('MED_DB_NAME', 'praxiapp'),
        'USER': os.getenv('MED_DB_USER', 'postgres'),
        'PASSWORD': os.getenv('MED_DB_PASSWORD') or os.getenv('PGPASSWORD', ''),
        'HOST': os.getenv('MED_DB_HOST', 'localhost'),
        'PORT': os.getenv('MED_DB_PORT', '5432'),
        'CONN_MAX_AGE': int(os.getenv('MED_DB_CONN_MAX_AGE', '0')),
    },
}


# Database routing:
# - Django-System-Apps + core migrieren nur in "default"
# - Auf "medical" werden nie Migrationen ausgeführt
DATABASE_ROUTERS = ['praxi_backend.db_router.PraxiAppRouter']


# Tests:
# - Nur "default" bekommt eine Test-DB.
# - "medical" bleibt mit der echten praxiapp verbunden (read-only in Tests).
TEST_RUNNER = 'praxi_backend.test_runner.PraxiAppTestRunner'


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Custom user model (must be set before running any migrations)
AUTH_USER_MODEL = 'core.User'


# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}


# SimpleJWT
JWT_SIGNING_KEY = os.getenv('JWT_SIGNING_KEY', SECRET_KEY)

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': JWT_SIGNING_KEY,
}


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static Files Configuration
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
    BASE_DIR / 'praxi_backend' / 'static',
]

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


CELERY_BROKER_URL = f"redis://{os.environ.get('REDIS_HOST')}:6379/0"
CELERY_RESULT_BACKEND = CELERY_BROKER_URL


# Static Files für Development
if DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'