from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

# ------------------------------------------------------------
# Paths / Env
# ------------------------------------------------------------

# base.py lives in: <BASE_DIR>/praxi_backend/settings/base.py
BASE_DIR = Path(__file__).resolve().parents[2]

# Load .env from repo root if present.
# - No exception if missing
# - Does not override real environment variables by default
load_dotenv(dotenv_path=BASE_DIR / ".env", override=False)


def _env(key: str, default: str | None = None) -> str | None:
    return os.getenv(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ------------------------------------------------------------
# Core
# ------------------------------------------------------------

SECRET_KEY = _env(
    "DJANGO_SECRET_KEY",
    "django-insecure-f((&w^a2svg9ajuahn!wf4s$xr1in)-1+jhi_4%5_2jc+-*=&$",
)

DEBUG = _env_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = [
    host.strip()
    for host in _env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],praxis-server,.local").split(",")
    if host.strip()
]


# ------------------------------------------------------------
# Apps / Middleware
# ------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    "rest_framework_simplejwt.token_blacklist",
    # PraxiApp
    "praxi_backend.core",
    "praxi_backend.appointments",
    "praxi_backend.patients",
    "praxi_backend.dashboard",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # must be before CommonMiddleware
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "praxi_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "praxi_backend.wsgi.application"
ASGI_APPLICATION = "praxi_backend.asgi.application"


# ------------------------------------------------------------
# Database (PostgreSQL only; DATABASE_URL required)
# ------------------------------------------------------------

_database_url = _env("DATABASE_URL")
if not _database_url:
    raise RuntimeError("DATABASE_URL is required and must point to PostgreSQL.")

db_cfg = dj_database_url.config(
    env="DATABASE_URL",
    conn_max_age=_env_int("SYS_DB_CONN_MAX_AGE", 60),
    ssl_require=False,
)

if db_cfg.get("ENGINE") != "django.db.backends.postgresql":
    raise RuntimeError("Only PostgreSQL is allowed; other engines are blocked.")

db_cfg.setdefault("OPTIONS", {})
db_cfg["OPTIONS"].setdefault("connect_timeout", _env_int("SYS_DB_CONNECT_TIMEOUT", 10))

DATABASES = {"default": db_cfg}

# Single-DB architecture; no routers.
DATABASE_ROUTERS: list[str] = []

TEST_RUNNER = "praxi_backend.test_runner.PraxiAppTestRunner"


# ------------------------------------------------------------
# Auth
# ------------------------------------------------------------

AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ------------------------------------------------------------
# REST / JWT
# ------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
}

JWT_SIGNING_KEY = _env("JWT_SIGNING_KEY", SECRET_KEY)

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=_env_int("JWT_ACCESS_MINUTES", 30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=_env_int("JWT_REFRESH_DAYS", 7)),
    "ALGORITHM": _env("JWT_ALGORITHM", "HS256"),
    "SIGNING_KEY": JWT_SIGNING_KEY,
}


# ------------------------------------------------------------
# I18N / TZ
# ------------------------------------------------------------

LANGUAGE_CODE = _env("DJANGO_LANGUAGE_CODE", "en-us")
TIME_ZONE = _env("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True


# ------------------------------------------------------------
# Static / Media
# ------------------------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

_static_dirs: list[Path] = []
for candidate in [BASE_DIR / "static", BASE_DIR / "praxi_backend" / "static"]:
    if candidate.exists():
        _static_dirs.append(candidate)
STATICFILES_DIRS = [str(p) for p in _static_dirs]

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(_env("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ------------------------------------------------------------
# CORS / CSRF
# ------------------------------------------------------------

CORS_ALLOW_ALL_ORIGINS = _env_bool("CORS_ALLOW_ALL_ORIGINS", default=DEBUG)
CORS_ALLOW_CREDENTIALS = _env_bool("CORS_ALLOW_CREDENTIALS", default=True)

CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in _env("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in _env(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
    ).split(",")
    if origin.strip()
]


# ------------------------------------------------------------
# Celery
# ------------------------------------------------------------

REDIS_HOST = _env("REDIS_HOST", "localhost")
REDIS_PORT = _env("REDIS_PORT", "6379")

CELERY_BROKER_URL = _env("CELERY_BROKER_URL") or f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_RESULT_BACKEND = _env("CELERY_RESULT_BACKEND") or CELERY_BROKER_URL

CELERY_TASK_ALWAYS_EAGER = _env_bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = _env_bool("CELERY_TASK_EAGER_PROPAGATES", default=True)


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

LOG_LEVEL = _env("LOG_LEVEL", "INFO")
LOG_DIR = Path(_env("DJANGO_LOG_DIR", str(BASE_DIR / "logs")))

# Only create log directory if filesystem is writable (not in Vercel serverless)
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
except (OSError, PermissionError):
    # Read-only filesystem (Vercel, AWS Lambda, etc.)
    # Use /tmp for logs or disable file logging
    LOG_DIR = Path("/tmp")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "kv": {
            "format": "%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "kv",
            "level": LOG_LEVEL,
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "kv",
            "level": LOG_LEVEL,
            "filename": str(LOG_DIR / "praxiapp.log"),
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": _env("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": _env("DJANGO_DB_LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
        "praxi_backend": {
            "handlers": ["console", "file"],
            "level": _env("PRAXI_LOG_LEVEL", LOG_LEVEL),
            "propagate": False,
        },
    },
}
