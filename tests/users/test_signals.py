"""Tests for users signals."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django_prometheus.testutils import assert_metric_diff, save_registry
from model_bakery import baker

if TYPE_CHECKING:
    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
def test_creating_user_increments_users_registered_total() -> None:
    """Creating a User increments users_registered_total by 1."""
    registry = save_registry()
    baker.make(User)
    assert_metric_diff(registry, 1, "users_registered_total")


@pytest.mark.django_db()
def test_updating_user_does_not_increment_users_registered_total(user_fixture: UserModel) -> None:
    """Updating a User does not increment users_registered_total."""
    registry = save_registry()
    user_fixture.username = "updated_username"
    user_fixture.save()
    assert_metric_diff(registry, 0, "users_registered_total")
