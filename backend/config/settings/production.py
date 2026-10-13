import os
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

os.environ["DJANGO_ENV"] = "production"

from .base import *  # noqa: E402,F403

DEBUG = False

if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")
if not REDIS_URL:  # noqa: F405
    raise ImproperlyConfigured("REDIS_URL must be set in production.")
if "*" in ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("A wildcard host is not allowed in production.")
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":  # noqa: F405
    raise ImproperlyConfigured("Production persistence must use PostgreSQL.")
try:
    redis_url = urlparse(REDIS_URL)  # noqa: F405
    redis_host = (redis_url.hostname or "").lower()
    redis_port = redis_url.port
except ValueError as error:
    raise ImproperlyConfigured("REDIS_URL must be a valid Redis URL.") from error
if redis_url.scheme not in {"redis", "rediss"} or not redis_host:
    raise ImproperlyConfigured("REDIS_URL must use redis:// or rediss:// with a host.")
if redis_port == 0:
    raise ImproperlyConfigured("REDIS_URL port must be a valid TCP port.")
if redis_host in {"localhost", "127.0.0.1", "::1"}:
    raise ImproperlyConfigured("Production Redis must not use a loopback host.")

# Railway terminates TLS at its edge. Trust this only while the app is reachable
# exclusively through the platform proxy and direct origin access is blocked.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
