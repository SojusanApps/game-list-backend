"""Tests for friendship request model."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model

from game_list.friendships.models import FriendshipRequest
from game_list.game_list.exceptions import ConflictException

if TYPE_CHECKING:
    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
def test_friendship_request_dunder_str(user_fixture: UserModel, admin_user_fixture: UserModel) -> None:
    """Test the `FriendshipRequest` dunder str method."""
    friendship_request = FriendshipRequest.objects.create(sender=user_fixture, receiver=admin_user_fixture)
    assert str(friendship_request) == (
        f"From: {friendship_request.sender.username} To: {friendship_request.receiver.username}"
    )


@pytest.mark.django_db()
def test_double_rejection_error(user_fixture: UserModel, admin_user_fixture: UserModel) -> None:
    """Check for double rejection error."""
    friendship_request = FriendshipRequest.objects.create(sender=user_fixture, receiver=admin_user_fixture)
    friendship_request.reject()

    with pytest.raises(ConflictException) as exception_info:
        friendship_request.reject()

    assert str(exception_info.value.detail) == "This friendship request is already rejected."
