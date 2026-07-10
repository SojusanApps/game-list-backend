"""Test ReportViewSet.create validation for Collection targets."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.collections.models import Collection
from my_game_list.moderation.models import ReportTargetType

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel


@pytest.mark.django_db()
def test_create_rejects_self_report_of_own_collection(
    authenticated_api_client: APIClient,
    user_fixture: UserModel,
) -> None:
    """A user cannot report their own collection."""
    own_collection = Collection.objects.create(name="my own collection", user=user_fixture)

    payload = {
        "target_type": ReportTargetType.COLLECTION,
        "target_collection": own_collection.id,
        "reason": "I regret naming this.",
    }
    response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db()
def test_create_rejects_second_pending_report_from_same_reporter_same_collection(
    authenticated_api_client: APIClient,
    other_user_collection_fixture: Collection,
) -> None:
    """A second pending report from the same reporter against the same collection is rejected."""
    payload = {
        "target_type": ReportTargetType.COLLECTION,
        "target_collection": other_user_collection_fixture.id,
        "reason": "First report.",
    }
    first_response = authenticated_api_client.post(reverse("moderation:reports-list"), payload, format="json")
    assert first_response.status_code == status.HTTP_201_CREATED

    second_response = authenticated_api_client.post(
        reverse("moderation:reports-list"),
        {**payload, "reason": "Second report."},
        format="json",
    )

    assert second_response.status_code == status.HTTP_400_BAD_REQUEST
