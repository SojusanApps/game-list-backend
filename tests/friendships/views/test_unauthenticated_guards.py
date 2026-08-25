"""Test the defensive is_authenticated guards inside the friendship viewsets.

These branches sit behind IsAuthenticated (class-level) or IsAuthenticated/IsAdminUser
(action-level) permission checks, which already reject an anonymous request before dispatch
ever reaches the view method. They are therefore unreachable through a normal API call and are
exercised here by invoking the viewset methods directly against a hand-built anonymous request.
"""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from my_game_list.friendships.models import FriendshipRequest
from my_game_list.friendships.serializers import FriendshipRequestCreateSerializer
from my_game_list.friendships.views import FriendshipRequestViewSet, FriendshipViewSet

if TYPE_CHECKING:
    from rest_framework.response import Response

_FACTORY = APIRequestFactory()


def _anonymous_request(method: str = "get") -> Request:
    """Build a DRF Request wrapping an anonymous user, bypassing the permission stack."""
    django_request = getattr(_FACTORY, method)("/")
    request = Request(django_request)
    request.user = AnonymousUser()
    return request


@pytest.mark.django_db()
def test_friendship_viewset_get_queryset_returns_none_for_unauthenticated_user() -> None:
    """FriendshipViewSet.get_queryset returns an empty queryset for an unauthenticated request."""
    viewset = FriendshipViewSet()
    viewset.request = _anonymous_request()

    assert list(viewset.get_queryset()) == []


@pytest.mark.django_db()
def test_friendship_request_viewset_get_queryset_returns_none_for_unauthenticated_user() -> None:
    """FriendshipRequestViewSet.get_queryset returns an empty queryset for an unauthenticated request."""
    viewset = FriendshipRequestViewSet()
    viewset.request = _anonymous_request()

    assert list(viewset.get_queryset()) == []


@pytest.mark.django_db()
def test_perform_create_is_a_noop_for_unauthenticated_user() -> None:
    """perform_create returns without saving anything when the request user isn't authenticated."""
    viewset = FriendshipRequestViewSet()
    viewset.request = _anonymous_request(method="post")
    serializer = FriendshipRequestCreateSerializer(data={})

    viewset.perform_create(serializer)

    assert FriendshipRequest.objects.count() == 0


@pytest.mark.django_db()
def test_accept_returns_401_for_unauthenticated_user() -> None:
    """The accept action returns 401 for an unauthenticated request, without touching get_object."""
    viewset = FriendshipRequestViewSet()
    request = _anonymous_request(method="post")

    response: Response = viewset.accept(request, pk=1)  # type: ignore[type-var, call-arg, misc]

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
