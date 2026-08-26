"""Tests for handling account-erasure events published by Keycloak."""

import uuid
from typing import TYPE_CHECKING, Any

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from model_bakery import baker

from game_list.games.models import GameFollow, GameReview
from game_list.users.keycloak_events import handle_keycloak_event

if TYPE_CHECKING:
    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


def _user_deleted_payload(sub: str, **overrides: Any) -> dict[str, Any]:  # noqa: ANN401
    payload = {
        "event": "user.deleted",
        "schema_version": 1,
        "realm": settings.KEYCLOAK_REALM,
        "sub": sub,
        "deleted_at": "2026-08-24T12:00:00Z",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db()
def test_user_deleted_event_erases_the_matching_account_and_everything_it_owns() -> None:
    """A user.deleted event permanently deletes the User and its owned data."""
    sub = str(uuid.uuid4())
    user = baker.make(User, keycloak_id=sub)
    review = baker.make(GameReview, user=user)
    follow = baker.make(GameFollow, user=user)

    handle_keycloak_event(_user_deleted_payload(sub))

    assert not User.objects.filter(pk=user.pk).exists()
    assert not GameReview.objects.filter(pk=review.pk).exists()
    assert not GameFollow.objects.filter(pk=follow.pk).exists()


@pytest.mark.django_db()
def test_user_deleted_event_erases_staff_and_superuser_accounts_too() -> None:
    """There is no staff/superuser exemption - the upstream event is trusted as-is."""
    sub = str(uuid.uuid4())
    user = baker.make(User, keycloak_id=sub, is_staff=True, is_superuser=True)

    handle_keycloak_event(_user_deleted_payload(sub))

    assert not User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db()
def test_user_deleted_event_for_unknown_sub_is_a_noop() -> None:
    """Redelivery after the account is already gone (or a sub that never existed) doesn't error."""
    handle_keycloak_event(_user_deleted_payload(str(uuid.uuid4())))


@pytest.mark.django_db()
def test_ignores_events_other_than_user_deleted() -> None:
    """An unsupported event type is logged and ignored, not treated as an error."""
    sub = str(uuid.uuid4())
    user = baker.make(User, keycloak_id=sub)

    handle_keycloak_event(_user_deleted_payload(sub, event="user.updated"))

    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db()
def test_ignores_unsupported_schema_versions() -> None:
    """An unsupported schema_version is logged and ignored, not treated as an error."""
    sub = str(uuid.uuid4())
    user = baker.make(User, keycloak_id=sub)

    handle_keycloak_event(_user_deleted_payload(sub, schema_version=2))

    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db()
def test_ignores_events_for_a_different_realm() -> None:
    """A realm mismatch is logged and ignored rather than acted on."""
    sub = str(uuid.uuid4())
    user = baker.make(User, keycloak_id=sub)

    handle_keycloak_event(_user_deleted_payload(sub, realm="some-other-realm"))

    assert User.objects.filter(pk=user.pk).exists()
