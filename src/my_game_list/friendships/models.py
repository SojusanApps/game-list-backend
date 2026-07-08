"""This module contains the model for the friendship related data."""

from typing import TYPE_CHECKING, ClassVar, Self

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from my_game_list.friendships.managers import FriendshipManager
from my_game_list.my_game_list.exceptions import ConflictException
from my_game_list.my_game_list.models import BaseModel

if TYPE_CHECKING:
    from collections.abc import Iterable


class Friendship(BaseModel):
    """A model representing the friendship relations of the users."""

    created_at = models.DateTimeField(_("creation time"), auto_now_add=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="friends",
        help_text="One party in the friendship.",
    )
    friend = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="_friends",
        help_text="The other party in the friendship.",
    )

    objects = FriendshipManager()

    class Meta(BaseModel.Meta):
        """Meta data for the friendship model."""

        verbose_name = _("friendship")
        verbose_name_plural = _("friendships")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("user", "friend"), name="unique_user_friend"),
        ]

    def __str__(self: Self) -> str:
        """String representation of the friendship model."""
        return f"User: {self.user.username}, Friend: {self.friend.username}"

    def save(  # type: ignore[override]
        self: Self,
        *args: Iterable[str] | str | bool | None,
        **kwargs: Iterable[str] | str | bool | None,
    ) -> None:
        """This method saves the friendship model."""
        if self.user == self.friend:
            raise ValidationError(_("The user cannot befriend himself."))
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def delete(self: Self, *args: bool | None, **kwargs: bool | None) -> tuple[int, dict[str, int]]:  # noqa: ARG002
        """This method deletes the friendship relationship."""
        user = self.user
        friend = self.friend
        return Friendship.objects.filter(user__in=(user, friend), friend__in=(friend, user)).delete()


class FriendshipRequest(BaseModel):
    """A model contains friendship requests."""

    message = models.CharField(
        _("message"),
        max_length=100,
        blank=True,
        help_text="An optional personal message accompanying the friendship request.",
    )
    rejected_at = models.DateTimeField(
        _("rejection time"),
        blank=True,
        null=True,
        help_text="Timestamp when the request was rejected, or null if not yet rejected.",
    )
    created_at = models.DateTimeField(_("creation time"), auto_now_add=True)
    last_modified_at = models.DateTimeField(_("last modified"), auto_now=True)

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_friend_requests",
        help_text="The user who sent the friendship request.",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_friend_requests",
        help_text="The user who received the friendship request.",
    )

    class Meta(BaseModel.Meta):
        """Meta data for the friendship request model."""

        verbose_name = _("friendship request")
        verbose_name_plural = _("friendship requests")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("sender", "receiver"), name="unique_sender_receiver"),
        ]

    def __str__(self: Self) -> str:
        """String representation of the friendship request model."""
        return f"From: {self.sender.username} To: {self.receiver.username}"

    def accept(self: Self) -> bool:
        """Accept this friendship request.

        Returns:
            bool: True after successful operation.
        """
        with transaction.atomic():
            Friendship.objects.create(user=self.sender, friend=self.receiver)
            Friendship.objects.create(user=self.receiver, friend=self.sender)
            self.delete()

        return True

    def reject(self: Self) -> bool:
        """Reject this friendship request.

        Returns:
            bool: True after successful operation.
        """
        if self.rejected_at is not None:
            raise ConflictException(_("This friendship request is already rejected."))
        self.rejected_at = timezone.now()
        self.save()

        return True
