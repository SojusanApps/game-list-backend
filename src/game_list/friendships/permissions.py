"""This module contains the custom permission classes for friendship requests."""

from typing import ClassVar

from game_list.game_list.permissions import IsOwner


class IsFriendshipRequestSender(IsOwner):
    """Permission to check if the user is the sender of a friendship request."""

    owner_field: ClassVar[str] = "sender"


class IsFriendshipRequestReceiver(IsOwner):
    """Permission to check if the user is the receiver of a friendship request."""

    owner_field: ClassVar[str] = "receiver"
