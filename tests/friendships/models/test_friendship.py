"""Tests for friendship model."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from game_list.friendships.models import Friendship

if TYPE_CHECKING:
    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
def test_friendship_dunder_str(user_and_admin_friendship_fixture: Friendship) -> None:
    """Test the `Friendship` dunder str method."""
    assert str(user_and_admin_friendship_fixture) == (
        f"User: {user_and_admin_friendship_fixture.user.username}, "
        f"Friend: {user_and_admin_friendship_fixture.friend.username}"
    )


@pytest.mark.django_db()
def test_friendship_to_myself(user_fixture: UserModel) -> None:
    """Test the self relationship is not possible."""
    with pytest.raises(ValidationError) as exception_info:
        Friendship.objects.create(user=user_fixture, friend=user_fixture)

    assert exception_info.value.message == "The user cannot befriend himself."
