"""This module contains the urls used within the moderation application."""

from django.urls import include, path
from rest_framework import routers

from my_game_list.moderation.views import ReportViewSet

app_name = "moderation"

router = routers.SimpleRouter()
router.register("reports", ReportViewSet, basename="reports")

urlpatterns = [
    path("", include(router.urls)),
]
