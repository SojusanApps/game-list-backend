"""This module contains the urls for the collections application."""

from django.urls import include, path
from rest_framework import routers

from game_list.collections.views import CollectionItemViewSet, CollectionViewSet

app_name = "collections"

router = routers.SimpleRouter()
router.register("collections", CollectionViewSet, basename="collections")
router.register("collection-items", CollectionItemViewSet, basename="collection-items")

urlpatterns = [
    path("", include(router.urls)),
]
