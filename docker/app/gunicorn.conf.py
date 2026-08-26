"""This module contains the configuration for the gunicorn."""

import multiprocessing
import os
from pathlib import Path
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

# Adds the request's trace id (stamped onto the X-Trace-Id response header by
# telemetry._add_trace_id_response_header) to the access log line, so a request can be found by
# the same id that correlates its app-level logs and its Tempo trace.
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" trace_id=%({x-trace-id}o)s'

_access_log_path = Path(oeg("GL_LOG_DIR_PATH", "/var/log/game_list/"), oeg("GL_LOG_FILENAME", "game_list.log"))

# gunicorn.glogging.Logger merges this dict on top of its own CONFIG_DEFAULTS with a shallow
# dict.update(), so every top-level key (loggers/handlers/formatters) must be given in full here,
# not just the "gunicorn.access" bits we actually want to change — otherwise the merge silently
# drops gunicorn's own console/error logging instead of extending it.
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        # propagate=False: Django's own dictConfig(LOGGING) reconfigures the root logger later
        # (per worker, after this runs), with handlers that apply the OTel-aware "color" formatter.
        # Left at gunicorn's own default of propagate=True, every gunicorn-logged line would also
        # re-appear via root — garbled with a fallback "trace_id=0" the second time around, since
        # the request span is already closed by the time gunicorn logs it.
        "gunicorn.error": {
            "level": "INFO",
            "handlers": ["error_console"],
            "propagate": False,
            "qualname": "gunicorn.error",
        },
        "gunicorn.access": {
            "level": "INFO",
            "handlers": ["console", "access_file"],
            "propagate": False,
            "qualname": "gunicorn.access",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "generic",
            "stream": "ext://sys.stdout",
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "formatter": "generic",
            "stream": "ext://sys.stderr",
        },
        "access_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": "generic",
            "filename": str(_access_log_path),
            "maxBytes": 5242880,  # 5*1024*1024 bytes (5MB)
            "backupCount": 5,
            "encoding": "utf8",
        },
    },
    "formatters": {
        "generic": {
            "format": "%(asctime)s [%(process)d] [%(levelname)s] %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter",
        },
    },
}


def post_fork(server: Any, worker: Any) -> None:  # NOSONAR(S1172) # noqa: ARG001 ANN401
    """Initialize telemetry in the worker process after fork."""
    setup_telemetry()
