"""Shared secure defaults for the API service.

Values are loaded from the process environment or a local, git-ignored .env file.
Production secrets are never synthesized here.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BACKEND_DIR.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
)
env.read_env(REPOSITORY_ROOT / ".env", overwrite=False)

ENVIRONMENT = env.str("DJANGO_ENV", default="development")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
SECRET_KEY = env.str("DJANGO_SECRET_KEY", default="")
if not SECRET_KEY and ENVIRONMENT != "test":
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY is required. Generate a unique local or deployment secret."
    )

default_allowed_hosts = (
    [] if ENVIRONMENT == "production" else ["localhost", "127.0.0.1"]
)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=default_allowed_hosts)
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

DATABASE_URL = env.str("DATABASE_URL", default="")
if not DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL is required outside the isolated test settings."
    )
DATABASES = {
    "default": env.db_url("DATABASE_URL"),
}
DATABASES["default"].update(
    {
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
        "CONN_HEALTH_CHECKS": True,
        "ATOMIC_REQUESTS": False,
    }
)
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"].setdefault("OPTIONS", {}).setdefault(
        "connect_timeout", env.int("DB_CONNECT_TIMEOUT", default=5)
    )

REDIS_URL = env.str("REDIS_URL", default="")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "agbofa-edutrack-local",
        }
    }

CELERY_BROKER_URL = env.str("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = None
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_TRACK_STARTED = False
CELERY_TIMEZONE = "UTC"
CELERY_ENABLE_UTC = True

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core.apps.CoreConfig",
    "identity.apps.IdentityConfig",
    "institutional.apps.InstitutionalConfig",
    "academic.apps.AcademicConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.RequestIdMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.PrivateApiCacheMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

AUTH_USER_MODEL = "identity.User"
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BACKEND_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_NAME = "edutrack_sessionid"
SESSION_COOKIE_AGE = env.int("SESSION_COOKIE_AGE", default=8 * 60 * 60)
SESSION_EXPIRE_AT_BROWSER_CLOSE = env.bool(
    "SESSION_EXPIRE_AT_BROWSER_CLOSE", default=True
)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_NAME = "edutrack_csrftoken"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"

# Identity controls are configurable, but recovery delivery remains disabled unless
# an Owner-approved adapter and expiry policy are explicitly configured.
MFA_ENCRYPTION_KEY = env.str("MFA_ENCRYPTION_KEY", default="")
IDENTITY_MFA_SETUP_TTL_SECONDS = env.int("IDENTITY_MFA_SETUP_TTL_SECONDS", default=300)
IDENTITY_RECOVERY_DELIVERY_BACKEND = env.str(
    "IDENTITY_RECOVERY_DELIVERY_BACKEND", default=""
)
IDENTITY_RECOVERY_TOKEN_TTL_SECONDS = env.int(
    "IDENTITY_RECOVERY_TOKEN_TTL_SECONDS", default=0
)
IDENTITY_LOGIN_RATE_LIMIT = env.str("IDENTITY_LOGIN_RATE_LIMIT", default="10/min")
IDENTITY_MFA_RATE_LIMIT = env.str("IDENTITY_MFA_RATE_LIMIT", default="10/min")
IDENTITY_RECOVERY_RATE_LIMIT = env.str("IDENTITY_RECOVERY_RATE_LIMIT", default="5/hour")

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_SSL_REDIRECT = False

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ("v1",),
    "VERSION_PARAM": "version",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_THROTTLE_RATES": {
        "identity_login": IDENTITY_LOGIN_RATE_LIMIT,
        "identity_mfa": IDENTITY_MFA_RATE_LIMIT,
        "identity_recovery": IDENTITY_RECOVERY_RATE_LIMIT,
    },
}

ACADEMIC_MOCK_APPROVER_ROLE_CODE = env.str(
    "ACADEMIC_MOCK_APPROVER_ROLE_CODE", default=""
)
ACADEMIC_MOCK_PREPARER_ROLE_CODE = env.str(
    "ACADEMIC_MOCK_PREPARER_ROLE_CODE", default=""
)
# An Owner-approved Basic 9 level code; empty by default so no BECE mock may run.
ACADEMIC_BECE_LEVEL_CODE = env.str("ACADEMIC_BECE_LEVEL_CODE", default="")
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024

LOG_LEVEL = env.str("LOG_LEVEL", default="INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "core.logging.JsonFormatter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

if ENVIRONMENT == "production" and DEBUG:
    raise ImproperlyConfigured("DJANGO_DEBUG must be false in production.")
