"""
Custom TUI command for game_list app.

Changed the hardcoded manage.py path, as in order to run management commands
the `uv run scripts/game-list-manage.py` command must be used.
"""

from typing import Any

from django_tui.management.commands.tui import Command as TuiCommand
from django_tui.management.commands.tui import DjangoTui


class CustomDjangoTui(DjangoTui):
    """Custom Django TUI with modified manage.py path."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Initialize the custom Django TUI."""
        super().__init__(*args, **kwargs)
        self.app_name = "uv run scripts/game-list-manage.py"


class Command(TuiCommand):  # # NOSONAR(S8443) - Already inheriting from BaseCommand
    """Custom TUI command for game_list app."""

    def handle(self, *args: Any, shell: bool = False, **options: Any) -> None:  # noqa: ANN401, ARG002
        """Handle the custom TUI command."""
        app = CustomDjangoTui(open_shell=shell)
        app.run()
