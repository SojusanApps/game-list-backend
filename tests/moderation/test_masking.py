"""Test the shared mask_if_moderated helper: the single seam deciding who sees real vs placeholder content."""

from typing import TYPE_CHECKING

import pytest

from game_list.moderation.masking import MODERATION_PLACEHOLDER_TEXT, mask_if_moderated

if TYPE_CHECKING:
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_returns_real_value_when_not_moderated(user_fixture: UserModel, other_user_fixture: UserModel) -> None:
    """An unmoderated value is returned unchanged, regardless of viewer."""
    result = mask_if_moderated("real text", moderated=False, owner=user_fixture, viewer=other_user_fixture)

    assert result == "real text"


@pytest.mark.django_db()
def test_returns_real_value_to_owner_when_moderated(user_fixture: UserModel) -> None:
    """A moderated value is still shown to its own owner."""
    result = mask_if_moderated("real text", moderated=True, owner=user_fixture, viewer=user_fixture)

    assert result == "real text"


@pytest.mark.django_db()
def test_returns_real_value_to_staff_when_moderated(
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
) -> None:
    """A moderated value is still shown to an is_staff viewer, even if they're not the owner."""
    result = mask_if_moderated("real text", moderated=True, owner=user_fixture, viewer=admin_user_fixture)

    assert result == "real text"


@pytest.mark.django_db()
def test_returns_placeholder_to_stranger_when_moderated(
    user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """A moderated value is replaced with the shared placeholder for a non-owner, non-staff viewer."""
    result = mask_if_moderated("real text", moderated=True, owner=user_fixture, viewer=other_user_fixture)

    assert result == str(MODERATION_PLACEHOLDER_TEXT)


@pytest.mark.django_db()
def test_exempt_owner_false_hides_from_owner_and_staff_too(
    user_fixture: UserModel,
    admin_user_fixture: UserModel,
) -> None:
    """With exempt_owner=False, the placeholder is returned for literally everyone, including owner/staff."""
    owner_result = mask_if_moderated(
        "real text",
        moderated=True,
        owner=user_fixture,
        viewer=user_fixture,
        exempt_owner=False,
    )
    staff_result = mask_if_moderated(
        "real text",
        moderated=True,
        owner=user_fixture,
        viewer=admin_user_fixture,
        exempt_owner=False,
    )

    assert owner_result == str(MODERATION_PLACEHOLDER_TEXT)
    assert staff_result == str(MODERATION_PLACEHOLDER_TEXT)
