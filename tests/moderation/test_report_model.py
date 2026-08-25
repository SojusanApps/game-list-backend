"""Test Report/ModerationWarning model behavior not covered by the ReportViewSet request cycle."""

from typing import TYPE_CHECKING

import pytest
from django.utils import translation
from rest_framework.exceptions import ValidationError

from game_list.moderation.models import ModerationWarning, Report, ReportTargetType, is_target_already_moderated

if TYPE_CHECKING:
    from game_list.games.models import GameReview
    from game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_report_str_includes_reporter_reported_user_target_type_and_status(
    user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
) -> None:
    """__str__ renders as '<reporter> -> <reported user> (<target_type>, <status>)'."""
    report = Report.objects.create(
        target_type=ReportTargetType.REVIEW,
        target_review=other_user_game_review_fixture,
        reported_by=user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_game_review_fixture.review,
        reason="Harassment.",
    )

    assert str(report) == f"{user_fixture.username} -> {other_user_fixture.username} (review, pending)"


@pytest.mark.django_db()
def test_is_target_already_moderated_reads_the_user_flag_for_avatar_and_username_targets(
    other_user_fixture: UserModel,
) -> None:
    """For avatar/username target types, moderation state comes from the flag on the User itself."""
    assert is_target_already_moderated(ReportTargetType.AVATAR, other_user_fixture) is False
    assert is_target_already_moderated(ReportTargetType.USERNAME, other_user_fixture) is False

    other_user_fixture.has_moderated_avatar = True
    other_user_fixture.save(update_fields=["has_moderated_avatar"])

    assert is_target_already_moderated(ReportTargetType.AVATAR, other_user_fixture) is True
    assert is_target_already_moderated(ReportTargetType.USERNAME, other_user_fixture) is False


@pytest.mark.django_db()
def test_is_target_already_moderated_falls_back_to_is_moderated_for_content_targets(
    other_user_game_review_fixture: GameReview,
) -> None:
    """For a content-row target_type (not avatar/username), moderation state comes from is_moderated."""
    assert is_target_already_moderated(ReportTargetType.REVIEW, other_user_game_review_fixture) is False

    other_user_game_review_fixture.is_moderated = True
    other_user_game_review_fixture.save(update_fields=["is_moderated"])

    assert is_target_already_moderated(ReportTargetType.REVIEW, other_user_game_review_fixture) is True


@pytest.mark.django_db()
def test_accept_raises_when_target_type_has_no_target_row(
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
) -> None:
    """Accepting a content-target report whose target FK was never set raises: nothing to flag.

    A Report created through ReportCreateSerializer can never end up in this state - the serializer
    requires the matching target field for a content target_type. Building the row directly via the
    ORM reaches the model's own defensive fallback in _apply_moderation_flag.
    """
    report = Report.objects.create(
        target_type=ReportTargetType.REVIEW,
        reported_by=other_user_fixture,
        reported_user=other_user_fixture,
        reported_value="",
        reason="Harassment.",
    )

    # Pin the active language so this assertion doesn't depend on whichever locale an earlier
    # test in the same session last activated (e.g. via an Accept-Language header).
    with translation.override("en"), pytest.raises(ValidationError) as exception_info:
        report.accept(admin_user_fixture)

    assert "not yet supported" in str(exception_info.value.detail)
    report.refresh_from_db()
    assert report.status == Report.StatusChoices.PENDING


@pytest.mark.django_db()
def test_moderation_warning_str_includes_username_and_issued_at(
    admin_user_fixture: UserModel,
    other_user_fixture: UserModel,
    other_user_game_review_fixture: GameReview,
) -> None:
    """__str__ renders as 'Warning for <username> (<issued_at>)'."""
    report = Report.objects.create(
        target_type=ReportTargetType.REVIEW,
        target_review=other_user_game_review_fixture,
        reported_by=admin_user_fixture,
        reported_user=other_user_fixture,
        reported_value=other_user_game_review_fixture.review,
        reason="Harassment.",
    )
    warning = ModerationWarning.objects.create(user=other_user_fixture, report=report, issued_by=admin_user_fixture)

    assert str(warning) == f"Warning for {other_user_fixture.username} ({warning.issued_at})"
