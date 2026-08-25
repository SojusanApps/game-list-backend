"""The single seam deciding who sees real content vs. the moderation placeholder."""

from typing import TYPE_CHECKING

from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from django.utils.functional import Promise

    from game_list.users.models import User

# Deliberately left as lazy translation proxies, not str - resolving them (via str()) at import
# time would freeze the placeholder to whichever language was active at process startup, instead
# of respecting each request's Accept-Language header (handled by LocaleMiddleware per-request).
MODERATION_PLACEHOLDER_TEXT = _("This content has been removed for violating our community guidelines.")
MODERATION_PLACEHOLDER_USERNAME = _("ModeratedUser")


def mask_if_moderated(  # noqa: PLR0913
    value: str,
    *,
    moderated: bool,
    owner: User | None,
    viewer: User,
    exempt_owner: bool = True,
    placeholder: str | Promise = MODERATION_PLACEHOLDER_TEXT,
) -> str:
    """Return value unchanged, or a placeholder, based on moderation state and who's asking.

    When exempt_owner is True (the default), the owner and any is_staff viewer still see the real
    value once moderated. When False, the placeholder is returned for literally everyone, including
    the owner and staff - used for has_moderated_avatar, where there's no legitimate reason to keep
    serving the flagged image back to anyone. owner may be None (e.g. a CollectionItem whose adding
    user was deleted) - it's simply never equal to a real viewer, so masking still applies correctly.

    placeholder defaults to the shared text placeholder (a lazy translation, resolved to a str only
    here - at call time, during request handling - so it respects the active per-request language
    rather than whatever was active at import time); pass "" for fields like gravatar_url where an
    empty value (not descriptive text) is the correct masked representation.
    """
    if not moderated:
        return value

    if exempt_owner and (viewer == owner or viewer.is_staff):
        return value

    return str(placeholder)
