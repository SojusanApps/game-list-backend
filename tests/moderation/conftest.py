"""The fixtures used within moderation test module."""

from typing import TYPE_CHECKING

import pytest
from freezegun import freeze_time
from model_bakery import baker

from game_list.collections.models import Collection, CollectionItem, CollectionMode
from game_list.games.models import (
    GameList,
    GameListStatus,
    GameReview,
    TranslationSuggestion,
    TranslationSuggestionField,
)
from game_list.moderation.models import Report, ReportTargetType

if TYPE_CHECKING:
    from collections.abc import Callable

    from game_list.games.models import Game
    from game_list.users.models import User as UserModel


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def other_user_fixture() -> UserModel:
    """A fixture with a second user, distinct from user_fixture, to own reported content."""
    return baker.make("users.User", username="other_user", email="other_user@email.com", password="test")  # noqa: S106


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def other_user_game_review_fixture(other_user_fixture: UserModel) -> GameReview:
    """A fixture with a game review owned by other_user_fixture, reportable by user_fixture."""
    game: Game = baker.make("games.Game")
    return GameReview.objects.create(
        review="This is a review with harassment in it.",
        recommendation=GameReview.Recommendation.NOT_RECOMMENDED,
        game=game,
        user=other_user_fixture,
    )


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def other_user_game_list_fixture(other_user_fixture: UserModel) -> GameList:
    """A fixture with a game list entry (and note) owned by other_user_fixture."""
    game: Game = baker.make("games.Game")
    return GameList.objects.create(
        status=GameListStatus.PLAYING,
        description="This note contains harassment in it.",
        game=game,
        user=other_user_fixture,
    )


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def other_user_translation_suggestion_fixture(other_user_fixture: UserModel) -> TranslationSuggestion:
    """A fixture with a translation suggestion submitted by other_user_fixture."""
    game: Game = baker.make("games.Game")
    return TranslationSuggestion.objects.create(
        game=game,
        field=TranslationSuggestionField.SUMMARY,
        submitted_by=other_user_fixture,
        current_value=game.summary_pl or "",
        proposed_value="This proposed translation contains harassment in it.",
    )


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def other_user_collection_fixture(other_user_fixture: UserModel) -> Collection:
    """A fixture with a collection owned by other_user_fixture."""
    return Collection.objects.create(
        name="This name contains harassment in it.",
        description="This description contains harassment in it.",
        user=other_user_fixture,
    )


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def collection_owner_fixture() -> UserModel:
    """A fixture with a third user who owns a collaborative collection but doesn't add items to it."""
    return baker.make("users.User", username="collection_owner", email="collection_owner@email.com")


@pytest.fixture
@freeze_time("2023-06-22 16:47:12")
def other_user_collection_item_fixture(
    collection_owner_fixture: UserModel,
    other_user_fixture: UserModel,
) -> CollectionItem:
    """A fixture with a collection item in a collaborative collection, added by other_user_fixture (not the owner)."""
    collection = Collection.objects.create(
        name="a collaborative collection",
        user=collection_owner_fixture,
        mode=CollectionMode.COLLABORATIVE,
    )
    game: Game = baker.make("games.Game")
    return CollectionItem.objects.create(
        collection=collection,
        game=game,
        added_by=other_user_fixture,
        description="This note contains harassment in it.",
    )


@pytest.fixture
def make_review_report(other_user_fixture: UserModel) -> Callable[..., Report]:
    """A factory for a pending Report against a GameReview, with sensible defaults any test can override."""

    def _make_review_report(
        reported_by: UserModel,
        target_review: GameReview,
        **overrides: object,
    ) -> Report:
        defaults = {
            "target_type": ReportTargetType.REVIEW,
            "target_review": target_review,
            "reported_by": reported_by,
            "reported_user": other_user_fixture,
            "reported_value": target_review.review,
            "reason": "Harassment.",
        }
        defaults.update(overrides)
        return Report.objects.create(**defaults)

    return _make_review_report
