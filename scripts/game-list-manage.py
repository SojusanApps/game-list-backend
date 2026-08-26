#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from typing import Self


class DjangoImportError(Exception):
    """Django import error."""

    def __init__(self: Self) -> None:
        """Set a error message."""
        super().__init__(
            "Couldn't import Django. Are you sure it's installed and available on your PYTHONPATH environment "
            "variable? Did you forget to activate a virtual environment?",
        )


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "game_list.settings.base")
    try:
        from django.core.management import execute_from_command_line  # noqa: PLC0415
    except ImportError as exc:
        raise DjangoImportError from exc

    # Only instrument the long-running dev server, not one-off commands like migrate/shell/test.
    # runserver's autoreloader spawns a fresh subprocess rather than forking, so there's no need
    # for the fork-safe post_fork/worker_process_init hooks that gunicorn and celery use.
    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        from game_list.game_list.telemetry import setup_telemetry  # noqa: PLC0415

        setup_telemetry()

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
