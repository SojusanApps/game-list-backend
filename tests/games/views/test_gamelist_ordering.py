"""Tests for ordering the game-lists API endpoint by the owner's score."""

from typing import TYPE_CHECKING, Any

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework import status
from rest_framework.reverse import reverse

from game_list.games.models import Game, GameList, GameListStatus

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


def _entry(user: UserModel, title: str, score: int | None, **game_kwargs: Any) -> GameList:  # noqa: ANN401
    """Create a game-list entry for a fresh game called `title`."""
    game_kwargs.setdefault("title_pl", title)
    game = baker.make(Game, title_en=title, **game_kwargs)
    return baker.make(GameList, game=game, user=user, score=score, status=GameListStatus.PLAYING)


def _ids(response: Any) -> list[int]:  # noqa: ANN401
    """Return the ids of the entries in a list response, in response order."""
    return [entry["id"] for entry in response.json()["results"]]


@pytest.mark.django_db()
def test_ordering_by_score_ascending(api_client: APIClient, user_fixture: UserModel) -> None:
    """`ordering=score` lists the lowest score first."""
    high = _entry(user_fixture, "High", 9)
    low = _entry(user_fixture, "Low", 2)
    mid = _entry(user_fixture, "Mid", 5)

    response = api_client.get(reverse("games:game-lists-list"), {"ordering": "score"})

    assert response.status_code == status.HTTP_200_OK
    assert _ids(response) == [low.id, mid.id, high.id]


@pytest.mark.django_db()
def test_ordering_by_score_descending(api_client: APIClient, user_fixture: UserModel) -> None:
    """`ordering=-score` lists the highest score first."""
    high = _entry(user_fixture, "High", 9)
    low = _entry(user_fixture, "Low", 2)
    mid = _entry(user_fixture, "Mid", 5)

    response = api_client.get(reverse("games:game-lists-list"), {"ordering": "-score"})

    assert response.status_code == status.HTTP_200_OK
    assert _ids(response) == [high.id, mid.id, low.id]


@pytest.mark.django_db()
@pytest.mark.parametrize("ordering", ["score", "-score"])
def test_ordering_by_score_puts_unscored_entries_last(
    api_client: APIClient,
    user_fixture: UserModel,
    ordering: str,
) -> None:
    """Unscored entries are 'no opinion yet': they come last in both directions."""
    unscored = _entry(user_fixture, "Aardvark", None)
    scored_low = _entry(user_fixture, "Low", 1)
    scored_high = _entry(user_fixture, "High", 10)

    response = api_client.get(reverse("games:game-lists-list"), {"ordering": ordering})

    expected_scored = [scored_low.id, scored_high.id] if ordering == "score" else [scored_high.id, scored_low.id]
    assert _ids(response) == [*expected_scored, unscored.id]


@pytest.mark.django_db()
@pytest.mark.parametrize("ordering", ["score", "-score"])
def test_ordering_by_score_breaks_ties_by_title_ascending(
    api_client: APIClient,
    user_fixture: UserModel,
    ordering: str,
) -> None:
    """Equal scores are ordered by game title A-Z, even when the score direction is descending."""
    zelda = _entry(user_fixture, "Zelda", 8)
    alpha = _entry(user_fixture, "Alpha", 8)
    mario = _entry(user_fixture, "Mario", 8)
    unscored_zed = _entry(user_fixture, "Zed", None)
    unscored_abe = _entry(user_fixture, "Abe", None)

    response = api_client.get(reverse("games:game-lists-list"), {"ordering": ordering})

    assert _ids(response) == [alpha.id, mario.id, zelda.id, unscored_abe.id, unscored_zed.id]


@pytest.mark.django_db()
def test_ordering_by_score_breaks_title_ties_by_id(api_client: APIClient, user_fixture: UserModel) -> None:
    """Entries whose score and title are both equal fall back to ascending `id`."""
    first = _entry(user_fixture, "Same Title", 7, slug="same-title-1")
    second = _entry(user_fixture, "Same Title", 7, slug="same-title-2")
    third = _entry(user_fixture, "Same Title", 7, slug="same-title-3")

    response = api_client.get(reverse("games:game-lists-list"), {"ordering": "-score"})

    assert _ids(response) == [first.id, second.id, third.id]


@pytest.mark.django_db()
def test_ordering_by_score_uses_polish_titles_for_tiebreak_with_english_fallback(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """With `Accept-Language: pl` ties follow the Polish title, falling back to English when it is blank."""
    alpha = _entry(user_fixture, "Alpha", 6, title_pl="Zeta")
    beta = _entry(user_fixture, "Beta", 6, title_pl="Gamma")
    delta = _entry(user_fixture, "Delta", 6, title_pl="")

    english = api_client.get(reverse("games:game-lists-list"), {"ordering": "score"}, HTTP_ACCEPT_LANGUAGE="en")
    polish = api_client.get(reverse("games:game-lists-list"), {"ordering": "score"}, HTTP_ACCEPT_LANGUAGE="pl")

    assert _ids(english) == [alpha.id, beta.id, delta.id]
    assert _ids(polish) == [delta.id, beta.id, alpha.id]


@pytest.mark.django_db()
def test_ordering_by_title_ascending(api_client: APIClient, user_fixture: UserModel) -> None:
    """`ordering=title` lists games A-Z regardless of score, unscored entries included in place."""
    zelda = _entry(user_fixture, "Zelda", 1)
    alpha = _entry(user_fixture, "Alpha", None)
    mario = _entry(user_fixture, "Mario", 10)

    response = api_client.get(reverse("games:game-lists-list"), {"ordering": "title"})

    assert response.status_code == status.HTTP_200_OK
    assert _ids(response) == [alpha.id, mario.id, zelda.id]


@pytest.mark.django_db()
def test_ordering_by_title_descending(api_client: APIClient, user_fixture: UserModel) -> None:
    """`ordering=-title` lists games Z-A."""
    zelda = _entry(user_fixture, "Zelda", 1)
    alpha = _entry(user_fixture, "Alpha", None)
    mario = _entry(user_fixture, "Mario", 10)

    response = api_client.get(reverse("games:game-lists-list"), {"ordering": "-title"})

    assert _ids(response) == [zelda.id, mario.id, alpha.id]


@pytest.mark.django_db()
@pytest.mark.parametrize("ordering", ["title", "-title"])
def test_ordering_by_title_breaks_ties_by_id(api_client: APIClient, user_fixture: UserModel, ordering: str) -> None:
    """Games sharing a title keep ascending `id` order in either title direction."""
    first = _entry(user_fixture, "Same Title", 1, slug="same-title-1")
    second = _entry(user_fixture, "Same Title", 9, slug="same-title-2")

    response = api_client.get(reverse("games:game-lists-list"), {"ordering": ordering})

    assert _ids(response) == [first.id, second.id]


@pytest.mark.django_db()
def test_ordering_by_title_uses_polish_titles_with_english_fallback(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """With `Accept-Language: pl` titles sort by the Polish title, falling back to English when it is blank."""
    alpha = _entry(user_fixture, "Alpha", 6, title_pl="Zeta")
    beta = _entry(user_fixture, "Beta", 6, title_pl="Gamma")
    delta = _entry(user_fixture, "Delta", 6, title_pl="")

    english = api_client.get(reverse("games:game-lists-list"), {"ordering": "title"}, HTTP_ACCEPT_LANGUAGE="en")
    polish = api_client.get(reverse("games:game-lists-list"), {"ordering": "title"}, HTTP_ACCEPT_LANGUAGE="pl")
    polish_descending = api_client.get(
        reverse("games:game-lists-list"),
        {"ordering": "-title"},
        HTTP_ACCEPT_LANGUAGE="pl",
    )

    assert _ids(english) == [alpha.id, beta.id, delta.id]
    assert _ids(polish) == [delta.id, beta.id, alpha.id]
    assert _ids(polish_descending) == [alpha.id, beta.id, delta.id]


@pytest.mark.django_db()
def test_ordering_combines_keys_in_the_order_given(api_client: APIClient, user_fixture: UserModel) -> None:
    """Comma-separated keys sort by the first key, then by the next; title A-Z is not appended on top."""
    b_high = _entry(user_fixture, "B", 9)
    a_high = _entry(user_fixture, "A", 9)
    c_low = _entry(user_fixture, "C", 2)
    d_unscored = _entry(user_fixture, "D", None)

    by_score_then_title_desc = api_client.get(reverse("games:game-lists-list"), {"ordering": "-score,-title"})
    by_title_then_score = api_client.get(reverse("games:game-lists-list"), {"ordering": "title,score"})

    assert _ids(by_score_then_title_desc) == [b_high.id, a_high.id, c_low.id, d_unscored.id]
    assert _ids(by_title_then_score) == [a_high.id, b_high.id, c_low.id, d_unscored.id]


@pytest.mark.django_db()
def test_ordering_by_title_replaces_title_filter_relevance_order(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """An explicit `ordering=-title` wins over the best-match-first order of the `title` filter."""
    best_match = _entry(user_fixture, "Half-Life", 5)
    weaker_match = _entry(user_fixture, "Half-Life 2: Episode One", 5)

    response = api_client.get(reverse("games:game-lists-list"), {"title": "half-life", "ordering": "-title"})

    assert _ids(response) == [weaker_match.id, best_match.id]


@pytest.mark.django_db()
def test_ordering_by_score_paginates_stably_across_ties(api_client: APIClient, user_fixture: UserModel) -> None:
    """Pages of tied scores neither repeat nor skip entries."""
    entries = [_entry(user_fixture, f"Game {index:02d}", 5) for index in range(30)]

    first_page = api_client.get(reverse("games:game-lists-list"), {"ordering": "-score"})
    second_page = api_client.get(reverse("games:game-lists-list"), {"ordering": "-score", "page": "2"})

    paged_ids = [*_ids(first_page), *_ids(second_page)]
    assert paged_ids == [entry.id for entry in entries]


@pytest.mark.django_db()
def test_ordering_replaces_title_filter_relevance_order(api_client: APIClient, user_fixture: UserModel) -> None:
    """Without `ordering` the best title match leads; an explicit score ordering wins over relevance."""
    best_match = _entry(user_fixture, "Half-Life", 1)
    weaker_match = _entry(user_fixture, "Half-Life 2: Episode One", 9)

    relevance = api_client.get(reverse("games:game-lists-list"), {"title": "half-life"})
    by_score = api_client.get(reverse("games:game-lists-list"), {"title": "half-life", "ordering": "-score"})

    assert _ids(relevance)[0] == best_match.id
    assert _ids(by_score) == [weaker_match.id, best_match.id]


@pytest.mark.django_db()
def test_ordering_by_score_composes_with_user_and_status_filters(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """Ordering applies on top of the other filters instead of replacing them."""
    other_user = baker.make(User, username="other_user", email="other@email.com")
    _entry(other_user, "Other User Game", 10)
    mine_low = _entry(user_fixture, "Mine Low", 3)
    mine_high = _entry(user_fixture, "Mine High", 8)
    game = baker.make(Game, title_en="Dropped", title_pl="Dropped")
    baker.make(GameList, game=game, user=user_fixture, score=10, status=GameListStatus.DROPPED)

    response = api_client.get(
        reverse("games:game-lists-list"),
        {"user": str(user_fixture.pk), "status": GameListStatus.PLAYING.value, "ordering": "-score"},
    )

    assert _ids(response) == [mine_high.id, mine_low.id]


@pytest.mark.django_db()
def test_ordering_by_score_is_available_to_authenticated_users(
    api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A logged-in user can order the list exactly as an anonymous visitor can."""
    api_client.force_authenticate(user=user_fixture)
    low = _entry(user_fixture, "Low", 1)
    high = _entry(user_fixture, "High", 10)

    response = api_client.get(reverse("games:game-lists-list"), {"ordering": "-score"})

    assert response.status_code == status.HTTP_200_OK
    assert _ids(response) == [high.id, low.id]


@pytest.mark.django_db()
def test_ordering_by_unknown_field_is_rejected(api_client: APIClient, user_fixture: UserModel) -> None:
    """Only `score` and `title` (with an optional `-` prefix) are accepted orderings."""
    _entry(user_fixture, "Any", 5)

    response = api_client.get(reverse("games:game-lists-list"), {"ordering": "playtime"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ordering" in response.json()


@pytest.mark.django_db()
def test_default_order_is_unchanged_without_ordering_param(api_client: APIClient, user_fixture: UserModel) -> None:
    """Without `ordering`, entries keep the model's default `id` order."""
    first = _entry(user_fixture, "Zulu", 1)
    second = _entry(user_fixture, "Alpha", 10)

    response = api_client.get(reverse("games:game-lists-list"))

    assert _ids(response) == [first.id, second.id]
