"""This module contains the urls for the friendships application."""

from django.urls import include, path
from rest_framework import routers

from game_list.friendships.views import FriendshipRequestViewSet, FriendshipViewSet

app_name = "friendships"

router = routers.SimpleRouter()
router.register("friendships", FriendshipViewSet, basename="friendships")
router.register("friendship-requests", FriendshipRequestViewSet, basename="friendship-requests")

urlpatterns = [
    path("", include(router.urls)),
]
