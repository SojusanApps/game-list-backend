"""Tests for the consume_keycloak_events management command's consumer wiring.

The actual event-handling logic (`handle_keycloak_event`) is covered by
tests/users/test_keycloak_events.py. This module only covers the kombu consumer
plumbing around it: `KeycloakEventsConsumer` and `Command.handle`.
"""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from django.conf import settings

from game_list.users.management.commands import consume_keycloak_events as consumer_module
from game_list.users.management.commands.consume_keycloak_events import Command, KeycloakEventsConsumer

if TYPE_CHECKING:
    import pytest


def test_get_consumers_builds_a_consumer_bound_to_the_deletion_queue() -> None:
    """The Consumer returned by get_consumers is bound to the pre-provisioned queue, without declaring it."""
    consumer = KeycloakEventsConsumer(MagicMock())
    mock_consumer_instance = MagicMock()
    consumer_cls = MagicMock(return_value=mock_consumer_instance)

    result = consumer.get_consumers(consumer_cls, channel=MagicMock())

    assert result == [mock_consumer_instance]
    consumer_cls.assert_called_once_with(
        queues=[consumer.queue],
        callbacks=[consumer.on_message],
        auto_declare=False,
        accept=["json"],
    )


def test_on_message_acks_after_successfully_handling_the_event(monkeypatch: pytest.MonkeyPatch) -> None:
    """A message that's handled without error is acked, never rejected."""
    mock_handle_keycloak_event = MagicMock()
    monkeypatch.setattr(consumer_module, "handle_keycloak_event", mock_handle_keycloak_event)
    consumer = KeycloakEventsConsumer(MagicMock())
    body = {"event": "user.deleted"}
    message = MagicMock()

    consumer.on_message(body, message)

    mock_handle_keycloak_event.assert_called_once_with(body)
    message.ack.assert_called_once_with()
    message.reject.assert_not_called()


def test_on_message_rejects_and_requeues_when_handling_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A message that fails to process is rejected and requeued, never acked, and doesn't propagate."""
    mock_handle_keycloak_event = MagicMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(consumer_module, "handle_keycloak_event", mock_handle_keycloak_event)
    consumer = KeycloakEventsConsumer(MagicMock())
    body = {"event": "user.deleted"}
    message = MagicMock()

    consumer.on_message(body, message)

    message.reject.assert_called_once_with(requeue=True)
    message.ack.assert_not_called()


def test_command_handle_opens_the_broker_connection_and_runs_the_consumer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Command.handle opens the configured broker connection and runs the consumer loop on it."""
    mock_connection_cls = MagicMock()
    monkeypatch.setattr(consumer_module, "Connection", mock_connection_cls)
    mock_run = MagicMock()
    monkeypatch.setattr(KeycloakEventsConsumer, "run", mock_run)

    Command().handle()

    mock_connection_cls.assert_called_once_with(settings.KEYCLOAK_EVENTS_BROKER_URL, heartbeat=10)
    mock_run.assert_called_once_with()
