"""Tests for user app models."""

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

if TYPE_CHECKING:
    from my_game_list.users.models import User as UserModel

User: type[UserModel] = get_user_model()


@pytest.mark.django_db()
def test_user_dunder_str(user_fixture: UserModel) -> None:
    """Test the `User` dunder str method."""
    assert str(user_fixture) == user_fixture.username


@pytest.mark.django_db()
def test_user_slug_collision_gets_suffixed(user_fixture: UserModel) -> None:
    """Two distinct usernames that slugify identically (differing only by case) don't collide."""
    assert user_fixture.username == "test_user"
    assert user_fixture.slug == "test_user"

    other_user = User.objects.create(username="Test_User", email="test-user-2@email.com")

    assert other_user.slug == "test_user-1"


@pytest.mark.django_db()
def test_user_keycloak_id_defaults_to_none(user_fixture: UserModel) -> None:
    """A User created outside the Keycloak flow (e.g. createsuperuser) has no keycloak_id, and that's fine."""
    assert user_fixture.keycloak_id is None


@pytest.mark.django_db()
def test_user_keycloak_id_is_unique_when_set() -> None:
    """Two Users can't share the same keycloak_id."""
    keycloak_id = "99999999-9999-9999-9999-999999999999"
    User.objects.create(username="user_one", email="user-one@email.com", keycloak_id=keycloak_id)

    with pytest.raises(IntegrityError):
        User.objects.create(username="user_two", email="user-two@email.com", keycloak_id=keycloak_id)


@pytest.mark.django_db()
def test_user_gravatar_tag_renders_an_img_pointing_at_the_gravatar_url(user_fixture: UserModel) -> None:
    """The admin gravatar preview is an <img> tag built from the user's gravatar_url."""
    tag = user_fixture.gravatar_tag

    assert tag == f'<img src={user_fixture.gravatar_url} width="125" height="150">'
