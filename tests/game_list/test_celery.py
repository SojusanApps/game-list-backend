"""Tests for the celery application configuration."""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from game_list.game_list import celery as celery_module

if TYPE_CHECKING:
    import pytest


def test_celery_worker_init_telemetry_calls_setup_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """The worker_process_init signal handler wires up telemetry for the celery worker process."""
    mock_setup_telemetry = MagicMock()
    monkeypatch.setattr(celery_module, "setup_telemetry", mock_setup_telemetry)

    celery_module.celery_worker_init_telemetry(sender=None)

    mock_setup_telemetry.assert_called_once_with()
