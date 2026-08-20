"""This module contains the moderation related models."""

from typing import TYPE_CHECKING, ClassVar, Self

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

from my_game_list.my_game_list.models import BaseModel
from my_game_list.notifications.constants import NotificationCategory, NotificationVerb
from my_game_list.notifications.utils import notify_send

if TYPE_CHECKING:
    from my_game_list.users.models import User

WARNING_THRESHOLD = 3


class ReportTargetType(models.TextChoices):
    """The kinds of things a Report can target."""

    AVATAR = "avatar", _("Avatar")
    USERNAME = "username", _("Username")
    REVIEW = "review", _("Review")
    TRANSLATION_SUGGESTION = "translation_suggestion", _("Translation Suggestion")
    GAME_LIST_NOTE = "game_list_note", _("GameList Note")
    COLLECTION = "collection", _("Collection")
    COLLECTION_ITEM_NOTE = "collection_item_note", _("Collection Item Note")


class ReportStatus(models.TextChoices):
    """The lifecycle states of a Report."""

    PENDING = "pending", _("Pending")
    ACCEPTED = "accepted", _("Accepted")
    REJECTED = "rejected", _("Rejected")


class ReportSource(models.TextChoices):
    """How a Report came to exist."""

    USER_SUBMITTED = "user_submitted", _("User submitted")
    ADMIN_DIRECT = "admin_direct", _("Admin direct")


# Target types whose moderation action is "flag the target row's own is_moderated field". Maps
# target_type to the Report attribute holding that target. AVATAR/USERNAME aren't here - their
# moderation action flags the reported User directly, not a content row.
_MODERATION_TARGET_ATTR: dict[str, str] = {
    ReportTargetType.REVIEW: "target_review",
    ReportTargetType.GAME_LIST_NOTE: "target_game_list",
    ReportTargetType.TRANSLATION_SUGGESTION: "target_translation_suggestion",
    ReportTargetType.COLLECTION: "target_collection",
    ReportTargetType.COLLECTION_ITEM_NOTE: "target_collection_item",
}

# Target types whose moderation action instead flags a boolean field directly on the reported User
# (no content row involved). Maps target_type to the User field name to set True.
_MODERATION_USER_FLAG_ATTR: dict[str, str] = {
    ReportTargetType.AVATAR: "has_moderated_avatar",
    ReportTargetType.USERNAME: "has_moderated_username",
}


def is_target_already_moderated(target_type: str, target: models.Model) -> bool:
    """Whether target is already flagged as moderated - target is the reported User for avatar/username."""
    user_flag_attr = _MODERATION_USER_FLAG_ATTR.get(target_type)
    if user_flag_attr:
        return bool(getattr(target, user_flag_attr))

    return bool(getattr(target, "is_moderated", False))


class Report(BaseModel):
    """A user's flag that another user's content or profile field violates the rules."""

    TargetType = ReportTargetType
    Status = ReportStatus
    Source = ReportSource

    target_type = models.CharField(
        _("target type"),
        max_length=25,
        choices=ReportTargetType.choices,
        help_text="What kind of thing this report targets.",
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="filed_reports",
        help_text="The user who filed this report.",
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_against",
        help_text="The user whose content or profile field is being reported.",
    )
    target_review = models.ForeignKey(
        "games.GameReview",
        on_delete=models.CASCADE,
        related_name="reports",
        null=True,
        blank=True,
        help_text="The GameReview this report targets, when target_type is review.",
    )
    target_translation_suggestion = models.ForeignKey(
        "games.TranslationSuggestion",
        on_delete=models.CASCADE,
        related_name="reports",
        null=True,
        blank=True,
        help_text="The TranslationSuggestion this report targets, when target_type is translation_suggestion.",
    )
    target_game_list = models.ForeignKey(
        "games.GameList",
        on_delete=models.CASCADE,
        related_name="reports",
        null=True,
        blank=True,
        help_text="The GameList this report targets (its note), when target_type is game_list_note.",
    )
    target_collection = models.ForeignKey(
        "collections.Collection",
        on_delete=models.CASCADE,
        related_name="reports",
        null=True,
        blank=True,
        help_text="The Collection this report targets, when target_type is collection.",
    )
    target_collection_item = models.ForeignKey(
        "collections.CollectionItem",
        on_delete=models.CASCADE,
        related_name="reports",
        null=True,
        blank=True,
        help_text="The CollectionItem this report targets (its note), when target_type is collection_item_note.",
    )
    reported_value = models.TextField(
        _("reported value"),
        blank=True,
        help_text="A snapshot of the offending text at submission time. Blank for avatar reports.",
    )
    reason = models.TextField(
        _("reason"),
        help_text="The reporter's free-text explanation of what's wrong.",
    )
    source = models.CharField(  # NOSONAR
        _("source"),
        max_length=20,
        choices=ReportSource.choices,
        default=ReportSource.USER_SUBMITTED,
        help_text="Whether this report was filed by an ordinary user, or created by an admin via direct moderation.",
    )
    status = models.CharField(  # NOSONAR
        _("status"),
        max_length=10,
        choices=ReportStatus.choices,
        default=ReportStatus.PENDING,
        help_text="The current lifecycle state of this report.",
    )
    submitted_at = models.DateTimeField(_("submitted at"), auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_reports",
        null=True,
        blank=True,
        help_text="The admin who accepted or rejected this report.",
    )
    reviewed_at = models.DateTimeField(
        _("reviewed at"),
        null=True,
        blank=True,
        help_text="The time this report was accepted or rejected.",
    )
    rejection_reason = models.CharField(
        _("rejection reason"),
        max_length=500,
        blank=True,
        help_text="Optional reason given by the admin when rejecting this report.",
    )

    class Meta(BaseModel.Meta):
        """Meta data for the report model."""

        verbose_name = _("report")
        verbose_name_plural = _("reports")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("reported_by", "target_review"),
                condition=models.Q(status=ReportStatus.PENDING),
                name="unique_pending_report_per_reporter_review",
            ),
            models.UniqueConstraint(
                fields=("reported_by", "target_translation_suggestion"),
                condition=models.Q(status=ReportStatus.PENDING),
                name="unique_pending_report_per_reporter_translation_suggestion",
            ),
            models.UniqueConstraint(
                fields=("reported_by", "target_game_list"),
                condition=models.Q(status=ReportStatus.PENDING),
                name="unique_pending_report_per_reporter_game_list",
            ),
            models.UniqueConstraint(
                fields=("reported_by", "target_collection"),
                condition=models.Q(status=ReportStatus.PENDING),
                name="unique_pending_report_per_reporter_collection",
            ),
            models.UniqueConstraint(
                fields=("reported_by", "target_collection_item"),
                condition=models.Q(status=ReportStatus.PENDING),
                name="unique_pending_report_per_reporter_collection_item",
            ),
            models.UniqueConstraint(
                fields=("reported_by", "reported_user", "target_type"),
                condition=models.Q(status=ReportStatus.PENDING, target_type=ReportTargetType.AVATAR),
                name="unique_pending_avatar_report_per_reporter",
            ),
            models.UniqueConstraint(
                fields=("reported_by", "reported_user", "target_type"),
                condition=models.Q(status=ReportStatus.PENDING, target_type=ReportTargetType.USERNAME),
                name="unique_pending_username_report_per_reporter",
            ),
        ]

    def __str__(self: Self) -> str:
        """String representation of the report model."""
        return f"{self.reported_by.username} -> {self.reported_user.username} ({self.target_type}, {self.status})"

    def _apply_moderation_flag(self: Self) -> None:
        """Flag the reported target as moderated, dispatching on target_type."""
        user_flag_attr = _MODERATION_USER_FLAG_ATTR.get(self.target_type)
        if user_flag_attr:
            setattr(self.reported_user, user_flag_attr, True)
            self.reported_user.save(update_fields=[user_flag_attr])
            return

        target_attr = _MODERATION_TARGET_ATTR.get(self.target_type)
        target = getattr(self, target_attr) if target_attr else None
        if target is None:
            message = _("Accepting a %(target_type)s report is not yet supported.") % {
                "target_type": self.target_type,
            }
            raise ValidationError(message)

        target.is_moderated = True
        target.save(update_fields=["is_moderated"])

    def accept(self: Self, admin_user: User, *, issue_warning: bool = True) -> ModerationWarning | None:
        """Accept this report: flag the target as moderated and, unless suppressed, issue one Warning.

        issue_warning=False is used only when this report is being closed as a duplicate of another
        report/direct-moderation action that already moderated the same target moments earlier in the
        same sweep - a target is warned once per moderation event, not once per Report naming it.
        """
        if self.status != ReportStatus.PENDING:
            message = _("Only a pending report can be accepted.")
            raise ValidationError(message)

        with transaction.atomic():
            self._apply_moderation_flag()

            self.status = ReportStatus.ACCEPTED
            self.reviewed_by = admin_user
            self.reviewed_at = timezone.now()
            self.save(update_fields=["status", "reviewed_by", "reviewed_at"])

            warning = None
            newly_banned = False
            if issue_warning:
                warning = ModerationWarning.objects.create(user=self.reported_user, report=self, issued_by=admin_user)

                if not self.reported_user.is_banned and self.reported_user.warnings.count() >= WARNING_THRESHOLD:
                    self.reported_user.is_banned = True
                    self.reported_user.banned_by = admin_user
                    self.reported_user.banned_at = timezone.now()
                    self.reported_user.ban_reason = f"Reached the warning threshold ({WARNING_THRESHOLD} warnings)."
                    self.reported_user.save(
                        update_fields=["is_banned", "banned_by", "banned_at", "ban_reason"],
                    )
                    newly_banned = True

        if issue_warning:
            notify_send(
                sender=admin_user,
                recipient=self.reported_user,
                verb=NotificationVerb.ACCOUNT_BANNED if newly_banned else NotificationVerb.WARNING_ISSUED,
                target=warning,
                category=NotificationCategory.MODERATION,
            )
        return warning

    def reject(self: Self, admin_user: User, rejection_reason: str = "") -> None:
        """Reject this report. No flag changes, no Warning, no notification."""
        if self.status != ReportStatus.PENDING:
            message = _("Only a pending report can be rejected.")
            raise ValidationError(message)

        self.status = ReportStatus.REJECTED
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.rejection_reason = rejection_reason
        self.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"])


class ModerationWarning(BaseModel):
    """One strike issued automatically and exactly once whenever a Report is accepted.

    Named `ModerationWarning` (not `Warning`, the domain term in CONTEXT.md) to avoid shadowing
    the builtin `Warning` exception class.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="warnings",
        help_text="The user this warning was issued to.",
    )
    report = models.OneToOneField(
        Report,
        on_delete=models.CASCADE,
        related_name="warning",
        help_text="The accepted report that caused this warning.",
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="issued_warnings",
        null=True,
        help_text="The admin who accepted the report and issued this warning.",
    )
    issued_at = models.DateTimeField(_("issued at"), auto_now_add=True)

    class Meta(BaseModel.Meta):
        """Meta data for the warning model."""

        verbose_name = _("warning")
        verbose_name_plural = _("warnings")

    def __str__(self: Self) -> str:
        """String representation of the warning model."""
        return f"Warning for {self.user.username} ({self.issued_at})"
