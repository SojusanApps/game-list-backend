# ruff: noqa: F403, F405, S108
"""This a configuration of the Django application for test runner."""

import os

os.environ["DJANGO_CORS_ALLOWED_ORIGINS"] = "https://test"
from game_list.settings.base import *  # NOSONAR

DEBUG = oeg("DJANGO_DEBUG", "False").lower() == "true"

# Overridden at runtime by the django_db_setup fixture in tests/conftest.py via testcontainers.
# These values are intentionally invalid to surface misconfiguration early.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "testcontainers_managed",
        "USER": "testcontainers_managed",
        "PASSWORD": "testcontainers_managed",  # NOSONAR
        "HOST": "localhost",
        "PORT": "0",
    },
}

REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = (
    "rest_framework.authentication.BasicAuthentication",
    "game_list.game_list.authentication.KeycloakAuthentication",
)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    },
}

# Speed up the password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

STATIC_URL = "/static/"
STATIC_ROOT = "/tmp/game-list/static/"  # NOSONAR

MEDIA_URL = "/media/"
MEDIA_ROOT = "/tmp/game-list/media/"  # NOSONAR
