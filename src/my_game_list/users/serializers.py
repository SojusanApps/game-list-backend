"""This module contains the serializers for user related data."""

from typing import TYPE_CHECKING, Any, ClassVar, Self

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import (
    validate_password as django_validate_password,
)
from django.db.models import Avg
from drf_spectacular.helpers import lazy_serializer
from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from my_game_list.games.models import GameListStatus
from my_game_list.moderation.masking import MODERATION_PLACEHOLDER_USERNAME, mask_if_moderated
from my_game_list.users.models import User as UserModel

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rest_framework.utils.serializer_helpers import ReturnDict

User: type[UserModel] = get_user_model()


def _masked_gravatar_url(instance: UserModel, viewer: UserModel) -> str:
    """Compute gravatar_url for a viewer, composing the two independent avatar-hiding triggers.

    has_moderated_avatar hides the avatar from literally everyone, including the owner and staff.
    is_banned alone hides it from other viewers only, exempting the owner (and staff) as usual.
    """
    if instance.has_moderated_avatar:
        return mask_if_moderated(
            instance.gravatar_url,
            moderated=True,
            owner=instance,
            viewer=viewer,
            exempt_owner=False,
            placeholder="",
        )
    return mask_if_moderated(
        instance.gravatar_url,
        moderated=instance.is_banned,
        owner=instance,
        viewer=viewer,
        placeholder="",
    )


def _masked_username(instance: UserModel, viewer: UserModel) -> str:
    """Mask username for other viewers if it's moderated or the user is banned. Standard exempt_owner rule."""
    return mask_if_moderated(
        instance.username,
        moderated=instance.has_moderated_username or instance.is_banned,
        owner=instance,
        viewer=viewer,
        placeholder=MODERATION_PLACEHOLDER_USERNAME,
    )


class UserCreateSerializer(serializers.ModelSerializer[UserModel]):
    """Serializer used during the user registration process."""

    class Meta:
        """Meta data for the class."""

        model = User
        fields = ("username", "password", "email", "gender")
        extra_kwargs: ClassVar[dict[str, dict[str, bool]]] = {"password": {"write_only": True}}

    def validate_password(self: Self, value: str) -> str:
        """The validation function for password."""
        django_validate_password(value)
        return value

    def create(self: Self, validated_data: Mapping[str, Any]) -> UserModel:
        """Create a new User instance."""
        user = User(
            username=validated_data["username"],
            email=validated_data["email"],
        )
        user.set_password(validated_data["password"])
        user.save()
        return user


class ChangeUsernameSerializer(serializers.ModelSerializer[UserModel]):
    """Serializer used to change a user's own username."""

    class Meta:
        """Meta data for the class."""

        model = User
        fields = ("username",)

    def validate_username(self: Self, value: str) -> str:
        """Reject submitting the current username as the 'new' one."""
        if self.instance is not None and value == self.instance.username:
            message = "The new username must be different from the current one."
            raise serializers.ValidationError(message)
        return value


class ChangePasswordSerializer(serializers.Serializer[UserModel]):
    """Serializer used to change a user's own password."""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_current_password(self: Self, value: str) -> str:
        """Check the current password against the requesting user."""
        user: UserModel = self.context["request"].user
        if not user.check_password(value):
            message = "Current password is incorrect."
            raise serializers.ValidationError(message)
        return value

    def validate_new_password(self: Self, value: str) -> str:
        """Validate the new password against Django's password validators."""
        django_validate_password(value)
        return value

    def validate(self: Self, attrs: dict[str, str]) -> dict[str, str]:
        """Check that new_password and new_password_confirm match."""
        if attrs["new_password"] != attrs["new_password_confirm"]:
            message = "The new password and its confirmation do not match."
            raise serializers.ValidationError(message)
        return attrs


class UserSimpleSerializer(serializers.ModelSerializer[UserModel]):
    """Simple user serializer."""

    gravatar_url = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()

    class Meta:
        """Meta data for the class."""

        model = User
        fields = ("id", "username", "gravatar_url", "slug", "is_staff")

    def get_gravatar_url(self: Self, instance: UserModel) -> str:
        """Mask the avatar for other viewers per the two independent avatar-hiding triggers."""
        viewer: UserModel = self.context["request"].user
        return _masked_gravatar_url(instance, viewer)

    def get_username(self: Self, instance: UserModel) -> str:
        """Mask the username for other viewers if it's moderated or the user is banned."""
        viewer: UserModel = self.context["request"].user
        return _masked_username(instance, viewer)


class UserSerializer(serializers.ModelSerializer[UserModel]):
    """Serializer for listing the user model."""

    gender = serializers.CharField(source="get_gender_display", read_only=True)
    gravatar_url = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()

    class Meta:
        """Meta data for the class."""

        model = User
        fields = (
            "id",
            "username",
            "email",
            "gender",
            "last_login",
            "last_active",
            "date_joined",
            "gravatar_url",
            "is_active",
            "slug",
            "is_staff",
        )
        read_only_fields = ("id", "last_login", "last_active", "date_joined", "slug")

    def get_gravatar_url(self: Self, instance: UserModel) -> str:
        """Mask the avatar for other viewers per the two independent avatar-hiding triggers."""
        viewer: UserModel = self.context["request"].user
        return _masked_gravatar_url(instance, viewer)

    def get_username(self: Self, instance: UserModel) -> str:
        """Mask the username for other viewers if it's moderated or the user is banned."""
        viewer: UserModel = self.context["request"].user
        return _masked_username(instance, viewer)


class UserDetailSerializer(serializers.ModelSerializer[UserModel]):
    """Detailed serializer for User model."""

    gender = serializers.CharField(source="get_gender_display", read_only=True)
    game_list_statistics = serializers.SerializerMethodField()
    friends = serializers.SerializerMethodField()
    latest_game_list_updates = serializers.SerializerMethodField()
    gravatar_url = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    warning_count = serializers.SerializerMethodField()

    class Meta:
        """Meta data for the class."""

        model = User
        fields = (
            "id",
            "username",
            "email",
            "gender",
            "last_login",
            "last_active",
            "date_joined",
            "gravatar_url",
            "game_list_statistics",
            "friends",
            "latest_game_list_updates",
            "slug",
            "is_staff",
            "warning_count",
        )

    def get_gravatar_url(self: Self, instance: UserModel) -> str:
        """Mask the avatar for other viewers per the two independent avatar-hiding triggers."""
        viewer: UserModel = self.context["request"].user
        return _masked_gravatar_url(instance, viewer)

    def get_username(self: Self, instance: UserModel) -> str:
        """Mask the username for other viewers if it's moderated or the user is banned."""
        viewer: UserModel = self.context["request"].user
        return _masked_username(instance, viewer)

    def get_warning_count(self: Self, instance: UserModel) -> int | None:
        """Get the number of moderation warnings issued to this user.

        Restricted to the profile owner and staff - a public warning count would be a shaming
        vector, the same reasoning that keeps is_banned unexposed everywhere in this feature.
        Returns None (not 0) for other viewers, so "hidden" is never confused with "no warnings".
        """
        viewer: UserModel = self.context["request"].user
        if viewer != instance and not viewer.is_staff:
            return None

        return instance.warnings.count()

    @extend_schema_field(
        inline_serializer(
            name="GameListStatisticsSerializer",
            fields={
                "completed": serializers.IntegerField(),
                "dropped": serializers.IntegerField(),
                "plan_to_play": serializers.IntegerField(),
                "on_hold": serializers.IntegerField(),
                "playing": serializers.IntegerField(),
                "total": serializers.IntegerField(),
                "mean_score": serializers.FloatField(),
            },
        ),
    )
    def get_game_list_statistics(self: Self, instance: UserModel) -> dict[str, int | float]:
        """Get the game list statistics for the user."""
        return {
            "completed": instance.game_lists.filter(status=GameListStatus.COMPLETED).count(),
            "dropped": instance.game_lists.filter(status=GameListStatus.DROPPED).count(),
            "plan_to_play": instance.game_lists.filter(status=GameListStatus.PLAN_TO_PLAY).count(),
            "on_hold": instance.game_lists.filter(status=GameListStatus.ON_HOLD).count(),
            "playing": instance.game_lists.filter(status=GameListStatus.PLAYING).count(),
            "total": instance.game_lists.count(),
            "mean_score": instance.game_lists.aggregate(mean_score=Avg("score"))["mean_score"],
        }

    @extend_schema_field(UserSimpleSerializer(many=True))
    def get_friends(self: Self, instance: UserModel) -> ReturnDict[Any, Any]:
        """Get the list of friends for the user limited to 5 friends."""
        friendships = instance.friends.all()[:5]
        friends = [friendship.friend for friendship in friendships]
        return UserSimpleSerializer(friends, many=True, context=self.context).data

    @extend_schema_field(
        lazy_serializer("my_game_list.games.serializers.GameListSerializer")(many=True),
    )
    def get_latest_game_list_updates(self: Self, instance: UserModel) -> ReturnDict[Any, Any]:
        """Get the latest game list updates for the user."""
        # Import needed at method level to avoid circular import
        from my_game_list.games.serializers import GameListSerializer  # noqa: PLC0415

        return GameListSerializer(
            instance.game_lists.all().order_by("-last_modified_at")[:5],
            many=True,
            context=self.context,
        ).data
