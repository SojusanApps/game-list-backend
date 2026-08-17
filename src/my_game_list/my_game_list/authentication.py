"""This module contains custom authentication classes."""

from functools import cache
from typing import TYPE_CHECKING, Any, Self

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from drf_spectacular.authentication import OpenApiAuthenticationExtension  # type: ignore[attr-defined]
from drf_spectacular.plumbing import build_bearer_security_scheme_object
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

if TYPE_CHECKING:
    from rest_framework.request import Request

    from my_game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@cache
def _get_jwks_client() -> jwt.PyJWKClient:
    """Return a lazily-created, process-wide PyJWKClient pointed at the realm's certs endpoint."""
    certs_url = f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}/protocol/openid-connect/certs"
    return jwt.PyJWKClient(certs_url, cache_keys=True)


def _unique_username(nickname: str, *, exclude_pk: int | None = None) -> str:
    """Resolve `nickname` to a username unique among `User.objects`, suffixing numerically on collision."""
    queryset = User.objects.all()
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)

    username = nickname
    counter = 2
    while queryset.filter(username=username).exists():
        username = f"{nickname}{counter}"
        counter += 1
    return username


class KeycloakAuthentication(BaseAuthentication):
    """Authenticates requests using Keycloak-issued access tokens, validated offline against the realm's JWKS."""

    def authenticate(self: Self, request: Request) -> tuple[UserModel, dict[str, Any]] | None:
        """Validate the request's Bearer token and resolve it to a local User."""
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        scheme, _, token = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            return None

        claims = self._decode_and_validate(token)
        user = self._resolve_user(claims)

        if not user.is_active:
            raise AuthenticationFailed

        return user, claims

    def _decode_and_validate(self: Self, token: str) -> dict[str, Any]:
        """Verify signature, issuer, audience, and required claims. Raises AuthenticationFailed on any failure."""
        expected_issuer = f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}"
        try:
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[signing_key.algorithm_name],
                issuer=expected_issuer,
                options={"verify_aud": False},
            )
        except jwt.exceptions.PyJWTError as exc:
            raise AuthenticationFailed from exc

        # Keycloak doesn't reliably put the client id in `aud` unless an audience mapper is
        # configured; `azp` carries it by default with no extra realm configuration (ADR-0012).
        aud = claims.get("aud", [])
        aud_claims = [aud] if isinstance(aud, str) else aud
        if settings.KEYCLOAK_AUDIENCE not in aud_claims and claims.get("azp") != settings.KEYCLOAK_AUDIENCE:
            raise AuthenticationFailed

        if not claims.get("nickname") or not claims.get("email"):
            raise AuthenticationFailed

        return claims

    def _resolve_user(self: Self, claims: dict[str, Any]) -> UserModel:
        """Look up or provision the local User for these claims, reconciling username on every call."""
        try:
            user = User.objects.get(keycloak_id=claims["sub"])
        except User.DoesNotExist:
            user = self._link_or_create_user(claims)
        else:
            self._sync_username(user, claims)

        return user

    def _link_or_create_user(self: Self, claims: dict[str, Any]) -> UserModel:
        """Provision a User for a never-seen sub: link an existing unlinked account by email, or create fresh.

        Linking is gated on `email_verified` so an unverified Keycloak signup can't claim someone
        else's existing account just by entering their email address (account-takeover vector).
        """
        if claims.get("email_verified"):
            existing_user = User.objects.filter(email=claims["email"], keycloak_id__isnull=True).first()
            if existing_user is not None:
                existing_user.keycloak_id = claims["sub"]
                existing_user.save()
                self._sync_username(existing_user, claims)
                return existing_user

        try:
            with transaction.atomic():
                user = User.objects.create(
                    keycloak_id=claims["sub"],
                    username=_unique_username(claims["nickname"]),
                    email=claims["email"],
                )
        except IntegrityError as exc:
            raise AuthenticationFailed from exc

        user.set_unusable_password()
        user.save()
        return user

    def _sync_username(self: Self, user: UserModel, claims: dict[str, Any]) -> None:
        """Sync `username` from the current `nickname` claim, regenerating slug (and owned Collection slugs).

        Only touches anything if `username` actually differs, and only regenerates slugs when it
        does - `User.slug`/`Collection.slug` are derived from `username`, so they go stale the
        moment it changes unless explicitly cleared (ADR-0003), same as the old change-username
        endpoint did before it was removed (ADR-0010).
        """
        if user.username == claims["nickname"]:
            return

        with transaction.atomic():
            user.username = _unique_username(claims["nickname"], exclude_pk=user.pk)
            user.slug = ""
            user.save()

            for collection in user.collections.all():
                collection.slug = ""
                collection.save()


class KeycloakAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    """Describes `KeycloakAuthentication` as a Bearer/JWT scheme in the generated OpenAPI schema."""

    target_class = KeycloakAuthentication
    name = "keycloakAuth"

    def get_security_definition(self: Self, auto_schema: Any) -> dict[str, Any]:  # noqa: ANN401, ARG002
        """Return the OpenAPI security scheme object for this authenticator."""
        return build_bearer_security_scheme_object(  # type: ignore[no-any-return, no-untyped-call]
            header_name="Authorization",
            token_prefix="Bearer",  # noqa: S106
            bearer_format="JWT",
        )
