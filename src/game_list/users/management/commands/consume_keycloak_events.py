"""Management command running the long-lived Keycloak account-erasure event consumer."""

import logging
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.core.management.base import BaseCommand
from kombu import Connection, Queue
from kombu.mixins import ConsumerMixin

from game_list.users.keycloak_events import handle_keycloak_event

if TYPE_CHECKING:
    from collections.abc import Callable

    from kombu import Consumer

logger = logging.getLogger(__name__)


class KeycloakEventsConsumer(ConsumerMixin):
    """Consumes events from the pre-provisioned `gamelist-backend.user-deletion` queue.

    The queue, its exchange, and its dead-letter setup are declared and bound entirely
    outside this codebase (see the `infrastructure` repo's RabbitMQ definitions) - this
    process only has read permission on that one queue, so it must never attempt to
    declare or bind anything itself.
    """

    def __init__(self, connection: Connection) -> None:
        """Bind to the connection this consumer will read from."""
        self.connection = connection
        self.queue = Queue(settings.KEYCLOAK_USER_DELETION_QUEUE, no_declare=True)

    def get_consumers(self, consumer_cls: Callable[..., Consumer], channel: Any) -> list[Any]:  # noqa: ANN401, ARG002
        """Build the consumer bound to the account-erasure queue."""
        return [
            consumer_cls(
                queues=[self.queue],
                callbacks=[self.on_message],
                auto_declare=False,
                accept=["json"],
            ),
        ]

    def on_message(self, body: Any, message: Any) -> None:  # noqa: ANN401
        """Process one message, acking only after it's been fully handled."""
        try:
            handle_keycloak_event(body)
        except Exception:
            logger.exception("Failed to process keycloak event, requeueing: %r", body)
            message.reject(requeue=True)
        else:
            message.ack()


class Command(BaseCommand):  # NOSONAR(S8443) - Already inheriting from BaseCommand
    """Run the long-lived Keycloak account-erasure event consumer."""

    help = "Consumes user.deleted events from RabbitMQ and permanently erases the matching account."

    def handle(self, *args: Any, **options: Any) -> None:  # noqa: ANN401, ARG002
        """Execute the command."""
        with Connection(settings.KEYCLOAK_EVENTS_BROKER_URL, heartbeat=10) as connection:
            KeycloakEventsConsumer(connection).run()
