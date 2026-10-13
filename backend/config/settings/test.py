import base64
import os
import secrets

# Force an isolated in-memory test database even when a developer's shell or
# repository .env contains shared-environment values. These settings are test-only.
os.environ["DJANGO_ENV"] = "test"
os.environ["DJANGO_DEBUG"] = "false"
os.environ["DJANGO_SECRET_KEY"] = secrets.token_urlsafe(64)  # pragma: allowlist secret
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = ""
os.environ["CELERY_BROKER_URL"] = ""

from .base import *  # noqa: E402,F403

DEBUG = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MFA_ENCRYPTION_KEY = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
IDENTITY_MFA_SETUP_TTL_SECONDS = 300
IDENTITY_RECOVERY_TOKEN_TTL_SECONDS = 900
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "edutrack-test-cache",
    }
}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
