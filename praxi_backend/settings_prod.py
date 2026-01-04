"""
Production Settings für PraxiApp Backend.

Verwendung:
    export DJANGO_SETTINGS_MODULE=praxi_backend.settings_prod
    gunicorn praxi_backend.wsgi:application

WICHTIG: Alle sensiblen Daten aus Umgebungsvariablen laden!
"""

import os
from .settings import *

# ---------------------------------------------------------
# PRODUCTION CORE SETTINGS
# ---------------------------------------------------------

DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() == 'true'

# Secret Key MUSS aus Umgebung kommen
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv('DJANGO_ALLOWED_HOSTS', '').split(',')
    if host.strip()
]

# ---------------------------------------------------------
# DATABASES: PostgreSQL
# ---------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['SYS_DB_NAME'],
        'USER': os.environ['SYS_DB_USER'],
        'PASSWORD': os.environ['SYS_DB_PASSWORD'],
        'HOST': os.getenv('SYS_DB_HOST', 'localhost'),
        'PORT': os.getenv('SYS_DB_PORT', '5432'),
        'CONN_MAX_AGE': int(os.getenv('SYS_DB_CONN_MAX_AGE', '60')),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    },
    'medical': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['MED_DB_NAME'],
        'USER': os.environ['MED_DB_USER'],
        'PASSWORD': os.environ['MED_DB_PASSWORD'],
        'HOST': os.getenv('MED_DB_HOST', 'localhost'),
        'PORT': os.getenv('MED_DB_PORT', '5432'),
        'CONN_MAX_AGE': int(os.getenv('MED_DB_CONN_MAX_AGE', '60')),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    },
}

DATABASE_ROUTERS = ['praxi_backend.db_router.PraxiAppRouter']

# ---------------------------------------------------------
# SECURITY SETTINGS
# ---------------------------------------------------------

# HTTPS/SSL
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Cookies
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

# HSTS (HTTP Strict Transport Security)
SECURE_HSTS_SECONDS = 31536000  # 1 Jahr
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Content Security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# CSRF
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

# ---------------------------------------------------------
# CORS (Nur spezifische Origins!)
# ---------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
]
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------
# STATIC FILES: WhiteNoise
# ---------------------------------------------------------

MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ---------------------------------------------------------
# REST FRAMEWORK: Nur JSON in Produktion
# ---------------------------------------------------------

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',  # Kein BrowsableAPI in Prod!
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}

# ---------------------------------------------------------
# JWT: Kürzere Token-Lifetime in Produktion
# ---------------------------------------------------------

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': os.environ.get('JWT_SIGNING_KEY', SECRET_KEY),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# ---------------------------------------------------------
# CELERY: Redis Broker
# ---------------------------------------------------------

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')

CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_ALWAYS_EAGER = False

# ---------------------------------------------------------
# CACHES: Redis
# ---------------------------------------------------------

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': f"redis://{REDIS_HOST}:{REDIS_PORT}/1",
    }
}

# ---------------------------------------------------------
# EMAIL
# ---------------------------------------------------------

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.example.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@praxiapp.com')

# ---------------------------------------------------------
# LOGGING: Production-Grade
# ---------------------------------------------------------

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            'format': '{"time": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s"}',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'praxiapp.log',
            'maxBytes': 10485760,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console', 'file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'praxi_backend': {
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}

# ---------------------------------------------------------
# SENTRY (Optional)
# ---------------------------------------------------------

SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
