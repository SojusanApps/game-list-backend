"""This module contains the fixture for the friendships application."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from game_list.friendships.models import Friendship, FriendshipRequest

if TYPE_CHECKING:
    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.fixture
@freeze_time("2023-06-23 08:21:12")
def user_and_admin_friendship_request_fixture(
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
) -> FriendshipRequest:
    """Add a friendship request between two users."""
    return FriendshipRequest.objects.create(sender=user_fixture, receiver=admin_user_fixture)


@pytest.fixture
@freeze_time("2023-06-23 08:21:12")
def user_and_admin_friendship_fixture(user_fixture: UserModel, admin_user_fixture: UserModel) -> Friendship:
    """Add a relationship between user_fixture and admin_user_fixture."""
    return Friendship.objects.create(user=user_fixture, friend=admin_user_fixture)
