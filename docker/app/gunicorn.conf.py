"""This module contains the configuration for the gunicorn."""

import multiprocessing
import os
from typing import Any

from game_list.game_list.telemetry import setup_telemetry

oeg = os.environ.get

bind = "0.0.0.0:8000"
reload = oeg("GUNICORN_RELOAD", "False").lower() == "true"
deamon = True
loglevel = oeg("GUNICORN_LOGLEVEL", "info")
errorlog = "-"
accesslog = "-"
timeout = int(oeg("GUNICORN_TIMEOUT", 300))
workers = multiprocessing.cpu_count() * 2 + 1


def post_fork(server: Any, worker: Any) -> None:  # NOSONAR(S1172) # noqa: ARG001 ANN401
    """Initialize telemetry in the worker process after fork."""
    setup_telemetry()
