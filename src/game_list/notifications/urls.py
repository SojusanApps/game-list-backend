"""This module contains the URL configuration for the notifications app."""

from rest_framework.routers import DefaultRouter

from game_list.notifications.views import NotificationViewSet

router = DefaultRouter()
router.register(r"", NotificationViewSet, basename="notification")

urlpatterns = router.urls
