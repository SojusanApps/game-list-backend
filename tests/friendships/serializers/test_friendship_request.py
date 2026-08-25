"""This module contains tests for the friendship request serializers."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from rest_framework.serializers import ValidationError

from my_game_list.friendships.serializers import FriendshipRequestCreateSerializer
from my_game_list.my_game_list.exceptions import SerializerValidationDetailError

if TYPE_CHECKING:
    from my_game_list.friendships.models import Friendship, FriendshipRequest
    from my_game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
def test_friendship_to_myself(user_fixture: UserModel) -> None:
    """Check for creation a friendship to the same user."""
    serializer = FriendshipRequestCreateSerializer(data={"sender": user_fixture.pk, "receiver": user_fixture.pk})

    with pytest.raises(ValidationError) as exception_info:
        serializer.is_valid(raise_exception=True)

    exc_detail = exception_info.value.detail
    if isinstance(exc_detail, list):
        raise SerializerValidationDetailError
    if isinstance(exc_list_detail := exc_detail["non_field_errors"], list):
        assert str(exc_list_detail[0]) == "Can't create friendship request to yourself."
    else:
        raise SerializerValidationDetailError


@pytest.mark.django_db()
def test_users_are_already_friends(
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
    user_and_admin_friendship_fixture: Friendship,  # noqa: ARG001
) -> None:
    """Test that users cant create a duplicated relationship."""
    serializer = FriendshipRequestCreateSerializer(data={"sender": user_fixture.pk, "receiver": admin_user_fixture.pk})

    with pytest.raises(ValidationError) as exception_info:
        serializer.is_valid(raise_exception=True)

    exc_detail = exception_info.value.detail
    if isinstance(exc_detail, list):
        raise SerializerValidationDetailError
    if isinstance(exc_list_detail := exc_detail["non_field_errors"], list):
        assert str(exc_list_detail[0]) == "You are already friends."
    else:
        raise SerializerValidationDetailError


@pytest.mark.django_db()
def test_you_already_sent_friendship_request(
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
    user_and_admin_friendship_request_fixture: FriendshipRequest,  # noqa: ARG001
) -> None:
    """Test that user can't send a another friendship request to the same user."""
    serializer = FriendshipRequestCreateSerializer(data={"sender": user_fixture.pk, "receiver": admin_user_fixture.pk})

    with pytest.raises(ValidationError) as exception_info:
        serializer.is_valid(raise_exception=True)

    exc_detail = exception_info.value.detail
    if isinstance(exc_detail, list):
        raise SerializerValidationDetailError
    if isinstance(exc_list_detail := exc_detail["non_field_errors"], list):
        assert str(exc_list_detail[0]) == ("The fields sender, receiver must make a unique set.")
    else:
        raise SerializerValidationDetailError


@pytest.mark.django_db()
def test_sender_already_sent_friendship_request_same_direction(
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
    user_and_admin_friendship_request_fixture: FriendshipRequest,  # noqa: ARG001
) -> None:
    """Test the sender-side duplicate message, reached by calling validate() directly.

    Going through is_valid() for this exact (sender, receiver) pair trips the model's
    unique_sender_receiver constraint (surfaced as a DRF UniqueTogetherValidator) before the
    custom validate() method ever runs, so that branch can only be exercised by calling
    validate() directly with already-resolved User instances, bypassing field-level validation.
    """
    serializer = FriendshipRequestCreateSerializer()

    with pytest.raises(ValidationError) as exception_info:
        serializer.validate({"message": "", "sender": user_fixture, "receiver": admin_user_fixture})

    # Called directly (bypassing is_valid/run_validation), the raised error isn't wrapped in a
    # {"non_field_errors": [...]} dict - that wrapping is applied by run_validation itself.
    exc_detail = exception_info.value.detail
    if isinstance(exc_detail, list):
        assert str(exc_detail[0]) == "You already sent a friendship request to this user."
    else:
        raise SerializerValidationDetailError


@pytest.mark.django_db()
def test_user_already_sent_friendship_request(
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
    user_and_admin_friendship_request_fixture: FriendshipRequest,  # noqa: ARG001
) -> None:
    """Test that user can't send a another friendship request to the same user."""
    serializer = FriendshipRequestCreateSerializer(data={"sender": admin_user_fixture.pk, "receiver": user_fixture.pk})

    with pytest.raises(ValidationError) as exception_info:
        serializer.is_valid(raise_exception=True)

    exc_detail = exception_info.value.detail
    if isinstance(exc_detail, list):
        raise SerializerValidationDetailError
    if isinstance(exc_list_detail := exc_detail["non_field_errors"], list):
        assert str(exc_list_detail[0]) == ("This user already sent a friendship request to you.")
    else:
        raise SerializerValidationDetailError
