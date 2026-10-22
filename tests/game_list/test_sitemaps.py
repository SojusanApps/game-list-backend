"""Tests for the sitemap views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.core.cache import cache
from django.test import override_settings
from model_bakery import baker
from rest_framework import status

from game_list.collections.models import Collection, CollectionVisibility
from game_list.games.models import Company, Game
from game_list.users.models import User

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rest_framework.test import APIClient

BASE_URL = "https://frontend.test"


@pytest.fixture(autouse=True)
def _sitemap_settings() -> Iterator[None]:
    cache.clear()
    with override_settings(SITEMAP_BASE_URL=BASE_URL):
        yield
    cache.clear()


@pytest.mark.django_db()
def test_index_lists_static_and_section_sitemaps(api_client: APIClient) -> None:
    """The index points at the static sitemap and at page 1 of every section, even when a section is empty."""
    response = api_client.get("/sitemap.xml")

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"].startswith("application/xml")
    body = response.content.decode()
    assert f"<loc>{BASE_URL}/sitemap-static.xml</loc>" in body
    for section in ("games", "companies", "collections", "profiles"):
        assert f"<loc>{BASE_URL}/sitemap-{section}-1.xml</loc>" in body


@pytest.mark.django_db()
def test_static_sitemap_lists_fixed_pages(api_client: APIClient) -> None:
    """The static sitemap lists the home page and the public informational pages."""
    body = api_client.get("/sitemap-static.xml").content.decode()

    assert f"<loc>{BASE_URL}/</loc>" in body
    assert f"<loc>{BASE_URL}/faq</loc>" in body


@pytest.mark.django_db()
def test_games_sitemap_uses_frontend_url_with_lastmod(api_client: APIClient) -> None:
    """Game entries use the frontend URL scheme /game/<id>/<slug> and carry a lastmod date."""
    game = baker.make(Game, slug="some-game")

    body = api_client.get("/sitemap-games-1.xml").content.decode()

    assert f"<loc>{BASE_URL}/game/{game.pk}/some-game</loc>" in body
    assert "<lastmod>" in body


@pytest.mark.django_db()
def test_companies_sitemap(api_client: APIClient) -> None:
    """Company entries use /company/<id>/<slug>."""
    company = baker.make(Company, slug="some-company")

    body = api_client.get("/sitemap-companies-1.xml").content.decode()

    assert f"<loc>{BASE_URL}/company/{company.pk}/some-company</loc>" in body


@pytest.mark.django_db()
def test_collections_sitemap_only_lists_public_collections(api_client: APIClient) -> None:
    """Private, friends-only and moderated collections must never be exposed."""
    owner = baker.make(User, is_active=True, is_banned=False)
    public = baker.make(Collection, user=owner, visibility=CollectionVisibility.PUBLIC, slug="public-one")
    baker.make(Collection, user=owner, visibility=CollectionVisibility.PRIVATE, slug="private-one")
    baker.make(Collection, user=owner, visibility=CollectionVisibility.FRIENDS, slug="friends-one")
    baker.make(Collection, user=owner, visibility=CollectionVisibility.PUBLIC, is_moderated=True, slug="moderated")

    body = api_client.get("/sitemap-collections-1.xml").content.decode()

    assert f"/collection/{public.pk}/public-one" in body
    assert "private-one" not in body
    assert "friends-one" not in body
    assert "moderated" not in body


@pytest.mark.django_db()
def test_profiles_sitemap_excludes_inactive_banned_and_masked_users(api_client: APIClient) -> None:
    """Only active, non-banned users with an unmasked username are listed."""
    visible = baker.make(User, is_active=True, is_banned=False, has_moderated_username=False, slug="visible")
    baker.make(User, is_active=False, slug="inactive")
    baker.make(User, is_active=True, is_banned=True, slug="banned")
    baker.make(User, is_active=True, has_moderated_username=True, slug="masked")

    body = api_client.get("/sitemap-profiles-1.xml").content.decode()

    assert f"/profile/{visible.pk}/visible" in body
    for hidden in ("inactive", "banned", "masked"):
        assert f"/{hidden}<" not in body


@pytest.mark.django_db()
@pytest.mark.parametrize("path", ["/sitemap-unknown-1.xml", "/sitemap-games-0.xml", "/sitemap-games-2.xml"])
def test_unknown_section_or_out_of_range_page_is_404(api_client: APIClient, path: str) -> None:
    """Unknown sections, page 0 and pages past the end return 404."""
    assert api_client.get(path).status_code == status.HTTP_404_NOT_FOUND
