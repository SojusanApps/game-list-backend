"""This module contains the celery application configuration."""

import os
from typing import Any

from celery import Celery
from celery.signals import worker_process_init

from game_list.game_list.telemetry import setup_telemetry

# set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "game_list.settings.base")

app = Celery("game_list")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()


@worker_process_init.connect(weak=False)
def celery_worker_init_telemetry(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001 ANN401
    """Initialize telemetry in the Celery worker process."""
    setup_telemetry()
