"""Test ReportCreateSerializer.validate: the target_type/target-reference guard rails."""

from typing import TYPE_CHECKING

import pytest
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.reverse import reverse
from rest_framework.test import APIRequestFactory

from my_game_list.moderation.serializers import ReportCreateSerializer

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel

_FACTORY = APIRequestFactory()


@pytest.mark.django_db()
def test_create_rejects_missing_target_field_for_target_type(
    authenticated_api_client: APIClient,
) -> None:
    """Submitting target_type=review without target_review is rejected: the field is required for that type."""
    response = authenticated_api_client.post(
        reverse("moderation:reports-list"),
        {"target_type": "review", "reason": "Harassment."},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "target_review" in response.data


@pytest.mark.django_db()
def test_validate_rejects_unsupported_target_type(user_fixture: UserModel) -> None:
    """An unsupported target_type is rejected by validate() directly.

    Every current ReportTargetType choice has an entry in _TARGET_SPECS, so the model's own
    ChoiceField validation already rejects any target_type outside that set before a normal
    request would ever reach the custom validate() method. This forward-compatible fallback (for
    a target_type added to the model without a matching _TARGET_SPECS entry yet) is exercised here
    by calling validate() directly with a target_type the choices don't recognize.
    """
    django_request = _FACTORY.post("/")
    django_request.user = user_fixture
    serializer = ReportCreateSerializer(context={"request": django_request})

    with pytest.raises(ValidationError) as exception_info:
        serializer.validate({"target_type": "unsupported_kind"})

    assert "target_type" in exception_info.value.detail
