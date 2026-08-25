"""Tests for the custom_tui management command."""

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from django.core.management import call_command

from my_game_list.my_game_list.management.commands.custom_tui import CustomDjangoTui

if TYPE_CHECKING:
    import pytest


def test_custom_django_tui_sets_app_name_to_the_uv_wrapper_script() -> None:
    """CustomDjangoTui points django-tui's generated commands at the uv wrapper, not the bare manage.py."""
    app = CustomDjangoTui()

    assert app.app_name == "uv run scripts/my-game-list-manage.py"


def test_call_command_runs_the_tui_without_opening_a_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling the command builds a CustomDjangoTui and runs it, without opening the interactive shell."""
    mock_run = MagicMock()
    monkeypatch.setattr(CustomDjangoTui, "run", mock_run)

    call_command("custom_tui")

    mock_run.assert_called_once_with()


def test_call_command_with_shell_option_opens_the_interactive_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """The --shell option is forwarded through to CustomDjangoTui as open_shell=True."""
    captured: dict[str, Any] = {}
    original_init = CustomDjangoTui.__init__

    def _capturing_init(self: CustomDjangoTui, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        captured.update(kwargs)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(CustomDjangoTui, "__init__", _capturing_init)
    monkeypatch.setattr(CustomDjangoTui, "run", MagicMock())

    call_command("custom_tui", shell=True)  # noqa: S604 -- Django's --shell flag, not subprocess shell=True

    assert captured.get("open_shell") is True
