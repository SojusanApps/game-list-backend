"""Models for the notification system."""

from typing import ClassVar, Self

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from game_list.notifications.constants import NotificationCategory, NotificationLevel


class NotificationQuerySet(models.QuerySet["Notification"]):
    """Custom QuerySet for notifications."""

    def unread(self) -> Self:
        """Return unread notifications."""
        return self.filter(unread=True)

    def mark_all_as_read(self) -> int:
        """Mark all notifications in the queryset as read."""
        return self.update(unread=False)


class Notification(models.Model):
    """A simple notification model."""

    recipient = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="The user who will receive the notification.",
        verbose_name=_("recipient"),
    )
    actor_content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        related_name="notify_actor",
        help_text="The content type of the actor.",
        verbose_name=_("actor content type"),
    )
    actor_object_id = models.PositiveIntegerField(
        verbose_name=_("actor object ID"),
        help_text="The object ID of the actor.",
    )
    actor = GenericForeignKey("actor_content_type", "actor_object_id")

    verb = models.CharField(verbose_name=_("verb"), max_length=255, help_text="The action performed.")
    description = models.TextField(
        verbose_name=_("description"),
        blank=True,
        help_text="Optional description of the notification.",
    )

    target_content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.CASCADE,
        related_name="notify_target",
        blank=True,
        null=True,
        help_text="The content type of the target.",
        verbose_name=_("target content type"),
    )
    target_object_id = models.PositiveIntegerField(
        verbose_name=_("target object ID"),
        blank=True,
        null=True,
        help_text="The object ID of the target.",
    )
    target = GenericForeignKey("target_content_type", "target_object_id")

    unread = models.BooleanField(
        verbose_name=_("unread"),
        default=True,
        db_index=True,
        help_text="Designates whether the notification is unread.",
    )
    level = models.CharField(
        verbose_name=_("level"),
        max_length=20,
        choices=NotificationLevel.choices,
        default=NotificationLevel.INFO,
        help_text="The level of the notification.",
    )
    category = models.CharField(
        verbose_name=_("category"),
        max_length=20,
        choices=NotificationCategory.choices,
        default=NotificationCategory.SYSTEM,
        help_text="The category of the notification.",
    )
    timestamp = models.DateTimeField(
        verbose_name=_("timestamp"),
        auto_now_add=True,
        help_text="The time the notification was created.",
    )
    data = models.JSONField(
        verbose_name=_("data"),
        blank=True,
        null=True,
        help_text="Optional JSON data for the notification.",
    )

    objects: models.Manager[Notification] = NotificationQuerySet.as_manager()

    class Meta:
        """Meta data for the notification model."""

        verbose_name = _("notification")
        verbose_name_plural = _("notifications")
        ordering = ("-timestamp",)
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["recipient", "unread"], name="notification_recip_unread_idx"),
        ]

    def __str__(self) -> str:
        """String representation of the notification."""
        return f"{self.actor} {self.verb} to {self.recipient}"

    def mark_as_read(self) -> None:
        """Mark the notification as read."""
        if self.unread:
            self.unread = False
            self.save()
