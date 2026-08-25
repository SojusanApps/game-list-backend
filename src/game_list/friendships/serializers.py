"""This module contains serializers for the friendship related data."""

from typing import TYPE_CHECKING, ClassVar, Self, TypedDict

from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from rest_framework.serializers import (
    ModelSerializer,
    SlugRelatedField,
    ValidationError,
)

from game_list.friendships.models import Friendship, FriendshipRequest
from game_list.users.serializers import UserSerializer

if TYPE_CHECKING:
    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


class FriendshipSerializer(ModelSerializer[Friendship]):
    """Serializer for listing friendships."""

    user = UserSerializer()
    friend = UserSerializer()

    class Meta:
        """Meta data for the friendship serializer."""

        model = Friendship
        fields = ("id", "created_at", "user", "friend")
        read_only_fields = ("id", "created_at")


class FriendshipRequestSerializer(ModelSerializer[FriendshipRequest]):
    """Serializer for listing the friendship requests."""

    sender = UserSerializer()
    receiver = UserSerializer()

    class Meta:
        """Meta data for the friendship request serializer."""

        model = FriendshipRequest
        fields: ClassVar[list[str]] = [
            "id",
            "rejected_at",
            "created_at",
            "last_modified_at",
            "message",
            "sender",
            "receiver",
        ]
        read_only_fields = ("id", "created_at")


class FriendshipRequestCreateSerializerDataType(TypedDict):
    """TypedDict representing the data structure for FriendshipRequestCreateSerializer."""

    message: str
    sender: UserModel
    receiver: UserModel


class FriendshipRequestCreateSerializer(ModelSerializer[FriendshipRequest]):
    """A serializer for creating a friendship request."""

    sender = SlugRelatedField(queryset=User.objects.all(), slug_field="id")
    receiver = SlugRelatedField(queryset=User.objects.all(), slug_field="id")

    class Meta(FriendshipRequestSerializer.Meta):
        """Meta data for the friendship request create serializer."""

        model = FriendshipRequest
        fields: ClassVar[list[str]] = ["message", "sender", "receiver"]

    def validate(
        self: Self,
        data: FriendshipRequestCreateSerializerDataType,
    ) -> FriendshipRequestCreateSerializerDataType:
        """Validate the data passed in the request."""
        sender = data["sender"]
        receiver = data["receiver"]
        if sender == receiver:
            raise ValidationError(_("Can't create friendship request to yourself."))

        if sender.friends.are_friends(sender, receiver):
            raise ValidationError(_("You are already friends."))

        if sender.friends.request_is_sent(sender, receiver):
            raise ValidationError(_("You already sent a friendship request to this user."))

        if sender.friends.request_is_sent(receiver, sender):
            raise ValidationError(_("This user already sent a friendship request to you."))

        return data
