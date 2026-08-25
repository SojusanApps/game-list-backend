"""Handles account-erasure events published by Keycloak onto the `gamelist-backend.user-deletion` queue."""

import logging
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

logger = logging.getLogger(__name__)

_SUPPORTED_EVENT = "user.deleted"
_SUPPORTED_SCHEMA_VERSION = 1


def handle_keycloak_event(payload: dict[str, Any]) -> None:
    """Process one message from the `gamelist-backend.user-deletion` queue.

    Only `user.deleted` events at `schema_version` 1, for our own realm, are understood
    right now. Anything else is logged and otherwise ignored rather than treated as an
    error, since the queue is expected to carry event types and schema versions this
    handler doesn't know about yet as the integration grows.
    """
    event = payload.get("event")
    schema_version = payload.get("schema_version")
    if event != _SUPPORTED_EVENT or schema_version != _SUPPORTED_SCHEMA_VERSION:
        logger.warning(
            "Ignoring unsupported keycloak event: event=%r schema_version=%r",
            event,
            schema_version,
        )
        return

    realm = payload.get("realm")
    if realm != settings.KEYCLOAK_REALM:
        logger.warning("Ignoring user.deleted event for unexpected realm: %r", realm)
        return

    _erase_account(payload["sub"])


def _erase_account(sub: str) -> None:
    """Permanently delete the User matching this Keycloak sub, and everything it owns.

    A deliberate exception to shadow moderation (see ADR-0018): the identity provider has
    already destroyed the account, so there's no owner left to preserve content for.
    Matching by `keycloak_id` and deleting via a filtered queryset makes this naturally
    idempotent - a sub with no matching User (already erased, or never existed) is a no-op,
    not an error, since the same event may be redelivered.
    """
    user_model = get_user_model()
    with transaction.atomic():
        deleted_count, _details = user_model.objects.filter(keycloak_id=sub).delete()

    if deleted_count == 0:
        logger.info("Received user.deleted for sub=%r with no matching account; no-op.", sub)
    else:
        logger.info("Erased account for sub=%r", sub)
