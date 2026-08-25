"""This module contains the urls used within the user application."""

from django.urls import include, path
from rest_framework import routers

from game_list.users.views import UserViewSet

app_name = "users"

router = routers.SimpleRouter()
router.register("users", UserViewSet, basename="users")

urlpatterns = [
    path("", include(router.urls)),
]
