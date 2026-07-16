"""Tests for user app models."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model

if TYPE_CHECKING:
    from my_game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
def test_user_dunder_str(user_fixture: UserModel) -> None:
    """Test the `User` dunder str method."""
    assert str(user_fixture) == user_fixture.username


@pytest.mark.django_db()
def test_user_slug_collision_gets_suffixed(user_fixture: UserModel) -> None:
    """Two distinct usernames that slugify identically (differing only by case) don't collide."""
    assert user_fixture.username == "test_user"
    assert user_fixture.slug == "test_user"

    other_user = User.objects.create(username="Test_User", email="test-user-2@email.com")

    assert other_user.slug == "test_user-1"
