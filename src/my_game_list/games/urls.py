"""This module contains the urls for the game application."""

from django.urls import include, path
from rest_framework import routers

from my_game_list.games.views import (
    CompanyViewSet,
    ExternalGameSourceViewSet,
    GameEngineViewSet,
    GameFollowViewSet,
    GameListViewSet,
    GameMediaViewSet,
    GameModeViewSet,
    GameReviewViewSet,
    GameStatusViewSet,
    GameTypeViewSet,
    GameViewSet,
    GenreViewSet,
    PlatformViewSet,
    PlayerPerspectiveViewSet,
    TranslationSuggestionViewSet,
)

app_name = "games"

router = routers.SimpleRouter()
router.register("companies", CompanyViewSet, basename="companies")
router.register("game-follows", GameFollowViewSet, basename="game-follows")
router.register("game-lists", GameListViewSet, basename="game-lists")
router.register("game-reviews", GameReviewViewSet, basename="game-reviews")
router.register("games", GameViewSet, basename="games")
router.register("genres", GenreViewSet, basename="genres")
router.register("platforms", PlatformViewSet, basename="platforms")
router.register("game-medias", GameMediaViewSet, basename="game-medias")
router.register("game-types", GameTypeViewSet, basename="game-types")
router.register("game-statuses", GameStatusViewSet, basename="game-statuses")
router.register("game-engines", GameEngineViewSet, basename="game-engines")
router.register("game-modes", GameModeViewSet, basename="game-modes")
router.register("player-perspectives", PlayerPerspectiveViewSet, basename="player-perspectives")
router.register("external-game-sources", ExternalGameSourceViewSet, basename="external-game-sources")
router.register("translation-suggestions", TranslationSuggestionViewSet, basename="translation-suggestions")

urlpatterns = [
    path("", include(router.urls)),
]
