"""
Django 5 settings for Inkwell project (12-Factor compliant).
"""

import sys
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, "dev-insecure-secret-key-change-in-production"),
    ALLOWED_HOSTS=(list, ["*"]),
    CSRF_TRUSTED_ORIGINS=(list, []),
    DATABASE_URL=(str, "postgres://postgres:postgres@localhost:5432/inkwell"),
    REDIS_URL=(str, ""),
    LOG_LEVEL=(str, "INFO"),
)

for _env_file in (BASE_DIR.parent.parent / ".env", BASE_DIR.parent / ".env", BASE_DIR / ".env"):
    if _env_file.is_file():
        environ.Env.read_env(str(_env_file))

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
LOG_LEVEL = env("LOG_LEVEL").upper()

INSTALLED_APPS = [
    "django_prometheus",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "blog.apps.BlogConfig",
]

MIDDLEWARE = [
    "my_medium.health.HealthCheckMiddleware",
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "my_medium.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "my_medium.wsgi.application"
ASGI_APPLICATION = "my_medium.asgi.application"

# Database configuration: PostgreSQL via DATABASE_URL in production, SQLite fallback in dev
# Uses django_prometheus.db.backends.* wrappers to expose django_db_* metrics.
PROMETHEUS_DB_ENGINES = {
    "django.db.backends.postgresql": "django_prometheus.db.backends.postgresql",
    "django.db.backends.psycopg2": "django_prometheus.db.backends.postgresql",
    "django.db.backends.sqlite3": "django_prometheus.db.backends.sqlite3",
    "django.db.backends.mysql": "django_prometheus.db.backends.mysql",
}

DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    db_config = env.db("DATABASE_URL")
    db_config["ENGINE"] = PROMETHEUS_DB_ENGINES.get(
        db_config["ENGINE"], db_config["ENGINE"]
    )
    DATABASES = {"default": db_config}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django_prometheus.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Export django_migrations_applied_total and django_migrations_unapplied_total
# (disabled automatically during build-time collectstatic so no DB connection is needed)
PROMETHEUS_EXPORT_MIGRATIONS = env.bool(
    "PROMETHEUS_EXPORT_MIGRATIONS",
    default="collectstatic" not in sys.argv,
)

# Stateless sessions stored in DB (no local disk state)
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# Redis & Celery configuration: eager fallback if REDIS_URL is unset
REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False
else:
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
CELERY_BEAT_SCHEDULE_FILENAME = env(
    "CELERY_BEAT_SCHEDULE_FILENAME",
    default="/tmp/celerybeat-schedule",
)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files served by WhiteNoise (works at build time without DB access)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "blog:login"
LOGIN_REDIRECT_URL = "blog:home"
LOGOUT_REDIRECT_URL = "blog:home"

# Structured JSON logging to stdout only
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["stdout"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": ["stdout"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "celery": {
            "handlers": ["stdout"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
