"""CI-only PostgreSQL test settings; requires a disposable database URL."""

import os

import environ
from django.core.exceptions import ImproperlyConfigured

from .test import *  # noqa: F403

DATABASE_URL = os.environ.get("EDUTRACK_CI_TEST_DATABASE_URL", "").strip()
if not DATABASE_URL.startswith(("postgres://", "postgresql://")):
    raise ImproperlyConfigured(
        "EDUTRACK_CI_TEST_DATABASE_URL must point to a disposable PostgreSQL database."
    )

# Override test.py's in-memory SQLite URL only in this explicit CI settings module.
os.environ["DATABASE_URL"] = DATABASE_URL
DATABASES = {"default": environ.Env.db_url_config(DATABASE_URL)}
DATABASES["default"].update(CONN_MAX_AGE=0, CONN_HEALTH_CHECKS=True)
