"""Tests for the Keycloak authentication class, exercised through real HTTP requests."""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.reverse import reverse

from my_game_list.collections.models import Collection

if TYPE_CHECKING:
    from collections.abc import Callable

    from rest_framework.test import APIClient

    from my_game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_valid_token_for_new_sub_creates_user_and_authenticates(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A valid token for a sub never seen before provisions a new User and the request succeeds."""
    token = make_keycloak_token(sub="11111111-1111-1111-1111-111111111111", nickname="new_kc_user")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    user = User.objects.get(keycloak_id="11111111-1111-1111-1111-111111111111")
    assert user.username == "new_kc_user"
    assert user.email == "kc_user@example.com"
    assert user.is_staff is False
    assert user.has_usable_password() is False


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_valid_token_for_known_sub_resolves_existing_user_without_duplicating(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A second request with the same sub resolves the same User instead of creating another one."""
    existing_user = User.objects.create(
        keycloak_id="22222222-2222-2222-2222-222222222222",
        username="known_kc_user",
        email="known_kc_user@example.com",
    )
    token = make_keycloak_token(sub="22222222-2222-2222-2222-222222222222", nickname="known_kc_user")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    assert User.objects.filter(keycloak_id="22222222-2222-2222-2222-222222222222").count() == 1
    assert User.objects.get(keycloak_id="22222222-2222-2222-2222-222222222222").pk == existing_user.pk


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_username_is_reconciled_from_current_nickname_claim(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A changed Keycloak nickname is synced onto the local User on the very next request."""
    User.objects.create(
        keycloak_id="33333333-3333-3333-3333-333333333333",
        username="stale_nickname",
        email="synced_user@example.com",
    )
    token = make_keycloak_token(sub="33333333-3333-3333-3333-333333333333", nickname="fresh_nickname")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    assert User.objects.get(keycloak_id="33333333-3333-3333-3333-333333333333").username == "fresh_nickname"


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_username_collision_on_sync_gets_a_numeric_suffix(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A nickname that collides with a different user's username is suffixed, not left to error."""
    User.objects.create(
        keycloak_id="44444444-4444-4444-4444-444444444444",
        username="popular_name",
        email="first_user@example.com",
    )
    User.objects.create(
        keycloak_id="55555555-5555-5555-5555-555555555555",
        username="second_user_old_name",
        email="second_user@example.com",
    )
    token = make_keycloak_token(sub="55555555-5555-5555-5555-555555555555", nickname="popular_name")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    second_user = User.objects.get(keycloak_id="55555555-5555-5555-5555-555555555555")
    assert second_user.username != "popular_name"
    assert second_user.username.startswith("popular_name")
    first_user = User.objects.get(keycloak_id="44444444-4444-4444-4444-444444444444")
    assert first_user.username == "popular_name"


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_is_staff_is_untouched_when_nickname_reconciles_and_admin_role_unchanged(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """Reconciling username alone doesn't perturb is_staff when the admin role claim is unchanged."""
    staff_user = User.objects.create(
        keycloak_id="66666666-6666-6666-6666-666666666666",
        username="staff_old_name",
        email="staff@example.com",
        is_staff=True,
    )
    token = make_keycloak_token(
        sub="66666666-6666-6666-6666-666666666666",
        nickname="staff_new_name",
        resource_access={settings.KEYCLOAK_CLIENT_ID: {"roles": ["admin"]}},
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    staff_user.refresh_from_db()
    assert staff_user.is_staff is True
    assert staff_user.username == "staff_new_name"


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_token_signed_by_wrong_key_is_rejected(api_client: APIClient) -> None:
    """A token signed by a key other than the one the (mocked) JWKS endpoint serves is rejected."""
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "nickname": "impostor",
            "email": "impostor@example.com",
            "iat": now,
            "exp": now + 300,
        },
        wrong_key,
        algorithm="RS256",
        headers={"kid": "test-kid"},
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not User.objects.filter(username="impostor").exists()


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_expired_token_is_rejected(api_client: APIClient, make_keycloak_token: Callable[..., str]) -> None:
    """An expired token is rejected, not silently accepted."""
    token = make_keycloak_token(exp=int(time.time()) - 10)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_token_from_wrong_issuer_is_rejected(api_client: APIClient, make_keycloak_token: Callable[..., str]) -> None:
    """A validly-signed token from an unexpected realm/issuer is rejected."""
    token = make_keycloak_token(iss="https://not-our-keycloak.example.com/realms/other-realm")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_token_with_wrong_client_id_in_both_aud_and_azp_is_rejected(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A token whose client id is in neither aud nor azp is rejected."""
    token = make_keycloak_token(aud="some-other-client", azp="some-other-client")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_token_is_accepted_with_client_id_in_azp_but_not_aud(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A token with the expected client id only in azp (not aud) is still accepted."""
    token = make_keycloak_token(aud="some-other-client")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_token_is_accepted_with_client_id_in_aud_but_not_azp(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A token with the expected client id only in aud (not azp) is still accepted."""
    token = make_keycloak_token(azp="some-other-client")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
@pytest.mark.parametrize("missing_claim", ["nickname", "email"])
def test_token_missing_required_claim_is_rejected(
    missing_claim: str,
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A token missing nickname or email fails closed instead of provisioning a broken User."""
    token = make_keycloak_token(omit=[missing_claim])
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not User.objects.exists()


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_deactivated_user_is_rejected_despite_valid_token(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A resolved User with is_active=False is rejected, even with an otherwise perfectly valid token."""
    User.objects.create(
        keycloak_id="88888888-8888-8888-8888-888888888888",
        username="deactivated_user",
        email="deactivated@example.com",
        is_active=False,
    )
    token = make_keycloak_token(sub="88888888-8888-8888-8888-888888888888", nickname="deactivated_user")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_new_sub_with_verified_email_links_to_existing_non_keycloak_user(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A bootstrapped admin (keycloak_id=None) logging in via Keycloak with the same, verified email gets linked."""
    admin = User.objects.create(
        keycloak_id=None,
        username="admin_bootstrap",
        email="shared@example.com",
        is_staff=True,
    )
    old_slug = admin.slug
    token = make_keycloak_token(
        sub="99999999-9999-9999-9999-999999999999",
        nickname="my_kc_nickname",
        email="shared@example.com",
        email_verified=True,
        resource_access={settings.KEYCLOAK_CLIENT_ID: {"roles": ["admin"]}},
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    assert User.objects.count() == 1
    admin.refresh_from_db()
    assert str(admin.keycloak_id) == "99999999-9999-9999-9999-999999999999"
    assert admin.username == "my_kc_nickname"
    assert admin.slug != old_slug
    assert admin.slug.startswith("my_kc_nickname")
    assert admin.is_staff is True


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_new_sub_with_unverified_email_colliding_with_existing_user_is_rejected(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """An unverified email colliding with an existing non-Keycloak account doesn't auto-link, and doesn't 500."""
    admin = User.objects.create(
        keycloak_id=None,
        username="admin_bootstrap",
        email="shared@example.com",
    )
    token = make_keycloak_token(
        sub="99999999-9999-9999-9999-999999999999",
        nickname="my_kc_nickname",
        email="shared@example.com",
        email_verified=False,
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert User.objects.count() == 1
    admin.refresh_from_db()
    assert admin.keycloak_id is None


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_username_reconciliation_regenerates_slug_and_owned_collection_slugs(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """Nickname sync regenerates User.slug and every owned Collection.slug, per ADR-0003."""
    user = User.objects.create(
        keycloak_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        username="stale_nickname",
        email="slug_sync_user@example.com",
    )
    old_user_slug = user.slug
    collection = Collection.objects.create(user=user, name="My Favorites")
    old_collection_slug = collection.slug
    assert old_user_slug.startswith("stale_nickname")
    assert old_collection_slug.startswith("stale_nickname")

    token = make_keycloak_token(sub="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", nickname="fresh_nickname")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    collection.refresh_from_db()
    assert user.username == "fresh_nickname"
    assert user.slug != old_user_slug
    assert user.slug.startswith("fresh_nickname")
    assert collection.slug != old_collection_slug
    assert collection.slug.startswith("fresh_nickname")


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_admin_role_grants_is_staff_on_create(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A never-seen sub whose token carries the client's "admin" role is created with is_staff=True."""
    token = make_keycloak_token(
        sub="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        nickname="new_admin",
        resource_access={settings.KEYCLOAK_CLIENT_ID: {"roles": ["admin"]}},
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    assert User.objects.get(keycloak_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb").is_staff is True


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_user_role_does_not_grant_is_staff_on_create(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A never-seen sub whose token only carries the "user" role is created with is_staff=False."""
    token = make_keycloak_token(
        sub="cccccccc-cccc-cccc-cccc-cccccccccccc",
        nickname="new_regular_user",
        resource_access={settings.KEYCLOAK_CLIENT_ID: {"roles": ["user"]}},
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    assert User.objects.get(keycloak_id="cccccccc-cccc-cccc-cccc-cccccccccccc").is_staff is False


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_admin_role_grants_is_staff_on_reconcile(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """An existing non-staff User whose token now carries the "admin" role is promoted."""
    User.objects.create(
        keycloak_id="dddddddd-dddd-dddd-dddd-dddddddddddd",
        username="promoted_user",
        email="promoted@example.com",
        is_staff=False,
    )
    token = make_keycloak_token(
        sub="dddddddd-dddd-dddd-dddd-dddddddddddd",
        nickname="promoted_user",
        resource_access={settings.KEYCLOAK_CLIENT_ID: {"roles": ["admin"]}},
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    assert User.objects.get(keycloak_id="dddddddd-dddd-dddd-dddd-dddddddddddd").is_staff is True


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_admin_role_absent_revokes_is_staff_on_reconcile(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """An existing staff User whose token no longer carries the "admin" role has it revoked."""
    User.objects.create(
        keycloak_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        username="demoted_user",
        email="demoted@example.com",
        is_staff=True,
    )
    token = make_keycloak_token(
        sub="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        nickname="demoted_user",
        resource_access={settings.KEYCLOAK_CLIENT_ID: {"roles": ["user"]}},
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    assert User.objects.get(keycloak_id="eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee").is_staff is False


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_admin_role_absent_revokes_is_staff_on_link(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """A bootstrapped admin (is_staff=True, keycloak_id=None) whose Keycloak token lacks "admin" is demoted on link."""
    admin = User.objects.create(
        keycloak_id=None,
        username="bootstrap_admin",
        email="bootstrap_admin@example.com",
        is_staff=True,
    )
    token = make_keycloak_token(
        sub="ffffffff-ffff-ffff-ffff-ffffffffffff",
        nickname="bootstrap_admin",
        email="bootstrap_admin@example.com",
        email_verified=True,
        resource_access={settings.KEYCLOAK_CLIENT_ID: {"roles": ["user"]}},
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    admin.refresh_from_db()
    assert admin.is_staff is False


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
@pytest.mark.parametrize(
    ("gender_claim", "expected_gender"),
    [
        pytest.param("male", "M", id="male"),
        pytest.param("female", "F", id="female"),
        pytest.param("prefer_not_to_say", "", id="prefer_not_to_say"),
    ],
)
def test_gender_claim_is_mapped_on_create(
    gender_claim: str,
    expected_gender: str,
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """The gender claim is mapped to Gender.MALE/FEMALE, or blank for "prefer_not_to_say"."""
    token = make_keycloak_token(
        sub="11111111-2222-3333-4444-555555555555",
        nickname="gendered_user",
        gender=gender_claim,
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    assert User.objects.get(keycloak_id="11111111-2222-3333-4444-555555555555").gender == expected_gender


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_missing_gender_claim_defaults_to_blank_on_create(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """No gender claim at all is treated the same as "prefer_not_to_say" - blank, not an error."""
    token = make_keycloak_token(sub="66666666-7777-8888-9999-000000000000", nickname="no_gender_user")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    assert User.objects.get(keycloak_id="66666666-7777-8888-9999-000000000000").gender == ""


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_gender_is_resynced_on_reconcile(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """An existing User's gender is updated to reflect the token's current gender claim."""
    User.objects.create(
        keycloak_id="12121212-3434-5656-7878-909090909090",
        username="regendering_user",
        email="regender@example.com",
        gender="M",
    )
    token = make_keycloak_token(
        sub="12121212-3434-5656-7878-909090909090",
        nickname="regendering_user",
        gender="female",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    assert User.objects.get(keycloak_id="12121212-3434-5656-7878-909090909090").gender == "F"


@pytest.mark.django_db()
@pytest.mark.usefixtures("_mock_keycloak_jwks")
def test_gender_is_synced_on_link(
    api_client: APIClient,
    make_keycloak_token: Callable[..., str],
) -> None:
    """Gender is synced for a bootstrapped account being linked by verified email, same as create/reconcile."""
    linked_user = User.objects.create(
        keycloak_id=None,
        username="link_gender_user",
        email="link_gender@example.com",
        gender="",
    )
    token = make_keycloak_token(
        sub="13131313-1414-1515-1616-171717171717",
        nickname="link_gender_user",
        email="link_gender@example.com",
        email_verified=True,
        gender="male",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    response = api_client.get(reverse("users:users-list"))

    assert response.status_code == status.HTTP_200_OK
    linked_user.refresh_from_db()
    assert linked_user.gender == "M"
