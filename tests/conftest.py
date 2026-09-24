"""Includes global scope fixtures. They can be used in all tests."""

import time
import uuid
from typing import TYPE_CHECKING, Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from freezegun import freeze_time
from model_bakery import baker
from rest_framework.test import APIClient
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import Reaper

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    import pytest_django
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

    from game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()

_POSTGRES_IMAGE = "postgres:18.4-alpine"


@pytest.fixture(scope="session")
def django_db_setup(
    django_test_environment: None,  # noqa: ARG001
    django_db_blocker: pytest_django.DjangoDbBlocker,
) -> Generator[None]:
    """Start a PostgreSQL container and wire it into Django settings for the test session."""
    with PostgresContainer(_POSTGRES_IMAGE) as postgres:
        settings.DATABASES["default"].update(
            {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": postgres.get_container_host_ip(),
                "PORT": str(postgres.get_exposed_port(5432)),
                "NAME": postgres.dbname,
                "USER": postgres.username,
                "PASSWORD": postgres.password,
            },
        )
        with django_db_blocker.unblock():
            call_command("migrate")
        yield
    # Stop Ryuk now, while pytest's output streams are still open. Left to testcontainers' atexit hook,
    # the teardown logs from docker/urllib3 hit already-closed streams and spam "--- Logging error ---".
    Reaper.delete_instance()


@pytest.fixture
@freeze_time("2023-05-25 12:01:12")
def user_fixture() -> UserModel:
    """Create a new user.

    Fixture creating and returning a user model instance with user name "test_user" and password "test".

    Returns:
        User: a created user instance
    """
    return baker.make(User, username="test_user", email="test@email.com", password="test")  # noqa: S106


@pytest.fixture
@freeze_time("2023-05-25 14:21:13")
def admin_user_fixture() -> UserModel:
    """Create a new admin.

    Fixture creating and returning a user model instance with superuser privileges,
    with user name "test_admin" and password "test".

    Returns:
        User: a created user instance
    """
    return baker.make(
        User,
        username="test_admin",
        email="test_admin@email.com",
        password="test",  # noqa: S106
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def api_client() -> APIClient:
    """Fixture providing the API client."""
    return APIClient()


@pytest.fixture
def authenticated_api_client(user_fixture: UserModel, api_client: APIClient) -> APIClient:
    """Fixture providing the API client that is authorized as a simple user."""
    api_client.force_authenticate(user_fixture)

    return api_client


@pytest.fixture
def admin_authenticated_api_client(admin_user_fixture: UserModel, api_client: APIClient) -> APIClient:
    """Fixture providing the API client that is authorized as a admin user."""
    api_client.force_authenticate(admin_user_fixture)

    return api_client


@pytest.fixture(scope="session")
def _keycloak_rsa_private_key() -> RSAPrivateKey:
    """A throwaway RSA keypair used to sign test tokens, standing in for Keycloak's own key."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def _mock_keycloak_jwks(_keycloak_rsa_private_key: RSAPrivateKey, monkeypatch: pytest.MonkeyPatch) -> None:
    """Make PyJWKClient return our test key instead of fetching from a real Keycloak server."""
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_keycloak_rsa_private_key.public_key(), as_dict=True)
    signing_key = jwt.PyJWK(public_jwk, algorithm="RS256")
    monkeypatch.setattr(jwt.PyJWKClient, "get_signing_key_from_jwt", lambda self, token: signing_key)  # noqa: ARG005


@pytest.fixture
def make_keycloak_token(_keycloak_rsa_private_key: RSAPrivateKey) -> Callable[..., str]:
    """Factory for a signed Keycloak-shaped test token, with sane defaults overridable per test."""

    def _make(omit: list[str] | None = None, **claim_overrides: Any) -> str:  # noqa: ANN401
        now = int(time.time())
        claims = {
            "sub": str(uuid.uuid4()),
            "nickname": "kc_user",
            "email": "kc_user@example.com",
            "email_verified": True,
            "iss": f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}",
            "aud": settings.KEYCLOAK_AUDIENCE,
            "azp": settings.KEYCLOAK_AUDIENCE,
            "iat": now,
            "exp": now + 300,
        }
        claims.update(claim_overrides)
        for claim_name in omit or []:
            claims.pop(claim_name, None)
        return jwt.encode(claims, _keycloak_rsa_private_key, algorithm="RS256", headers={"kid": "test-kid"})

    return _make
