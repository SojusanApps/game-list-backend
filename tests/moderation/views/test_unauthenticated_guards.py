"""Test the defensive is_authenticated guards inside ReportViewSet.

These branches sit behind IsAuthenticated (class-level) or IsAdminUser (action-level) permission
checks, which already reject an anonymous request before dispatch ever reaches the view method.
They are therefore unreachable through a normal API call and are exercised here by invoking the
viewset methods directly against a hand-built anonymous request.
"""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import AnonymousUser
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from game_list.moderation.views import ReportViewSet

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
def test_get_queryset_returns_none_for_unauthenticated_user() -> None:
    """ReportViewSet.get_queryset returns an empty queryset for an unauthenticated request."""
    viewset = ReportViewSet()
    viewset.request = _anonymous_request()

    assert list(viewset.get_queryset()) == []


@pytest.mark.django_db()
def test_direct_moderate_returns_401_for_unauthenticated_user() -> None:
    """The direct_moderate action returns 401 for an unauthenticated request."""
    viewset = ReportViewSet()
    request = _anonymous_request(method="post")

    response: Response = viewset.direct_moderate(request)  # type: ignore[type-var, call-arg, misc]

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_accept_returns_401_for_unauthenticated_user() -> None:
    """The accept action returns 401 for an unauthenticated request, without touching get_object."""
    viewset = ReportViewSet()
    request = _anonymous_request(method="post")

    response: Response = viewset.accept(request, pk="1")  # type: ignore[type-var, call-arg, misc]

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
def test_reject_returns_401_for_unauthenticated_user() -> None:
    """The reject action returns 401 for an unauthenticated request, without touching get_object."""
    viewset = ReportViewSet()
    request = _anonymous_request(method="post")

    response: Response = viewset.reject(request, pk="1")  # type: ignore[type-var, call-arg, misc]

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
