# ruff: noqa: F403, F405
"""This is a configuration of the Django application for mypy type checker."""

from game_list.settings.base import *  # NOSONAR

# Remove django_prometheus to avoid duplicate metrics in type-checking
# Metrics are not needed during type-checking
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django_prometheus"]
