"""Constants for the notifications app."""

from django.db.models import TextChoices
from django.utils.translation import gettext_lazy as _


class NotificationLevel(TextChoices):
    """Level choices for a notification."""

    INFO = "info", _("Info")
    SUCCESS = "success", _("Success")
    WARNING = "warning", _("Warning")
    ERROR = "error", _("Error")


class NotificationCategory(TextChoices):
    """Category choices for a notification."""

    SYSTEM = "system", _("System")
    FRIENDSHIP = "friendship", _("Friendship")
    RELEASE = "game_release", _("Game Release")
    TRANSLATION_SUGGESTION = "translation", _("Translation Suggestion")


class NotificationVerb(TextChoices):
    """Verb choices for a notification. Values are stored in English in the database."""

    FRIEND_REQUEST_SENT = "sent you a friend request", _("sent you a friend request")
    FRIEND_REQUEST_ACCEPTED = "accepted your friend request", _("accepted your friend request")
    GAME_PREMIERES_TODAY = "premieres today!", _("premieres today!")
    GAME_PREMIERES_IN_A_WEEK = "premieres in a week!", _("premieres in a week!")
    TRANSLATION_SUGGESTION_ACCEPTED = (
        "accepted your translation suggestion",
        _("accepted your translation suggestion"),
    )
    TRANSLATION_SUGGESTION_REJECTED = (
        "rejected your translation suggestion",
        _("rejected your translation suggestion"),
    )


class NotificationDescription(TextChoices):
    """Description templates for notifications. Values are stored in English in the database."""

    GAME_PREMIERES_TODAY = "{game} is out now. Time to play!", _("{game} is out now. Time to play!")
    GAME_PREMIERES_IN_A_WEEK = "{game} will be released in 7 days.", _("{game} will be released in 7 days.")
