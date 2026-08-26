# ruff: noqa: F403, F405
"""This a configuration of the Django application for local development purposes."""

from game_list.settings.base import *  # NOSONAR

DEBUG = oeg("DJANGO_DEBUG", "True").lower() == "true"

INSTALLED_APPS += [
    "rosetta",
    "django_tui",
]

CORS_ALLOWED_ORIGINS = ["http://localhost:5173"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:5173"]

REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = (
    "rest_framework.authentication.BasicAuthentication",
    "game_list.game_list.authentication.KeycloakAuthentication",
)

STATIC_URL = "/static/"
STATIC_ROOT = f"/{BASE_DIR.parent}/static/"

MEDIA_URL = "/media/"
MEDIA_ROOT = f"/{BASE_DIR.parent}/media/"
