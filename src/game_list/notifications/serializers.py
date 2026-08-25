"""This module contains serializers for the notification system."""

from typing import Any

from django.contrib.auth import get_user_model
from django.utils.translation import get_language, gettext
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from game_list.notifications.models import Notification

User = get_user_model()


class NotificationGenericActorSerializer(serializers.Serializer[Any]):
    """Serializer for generic notification actors."""

    id = serializers.IntegerField()
    str = serializers.CharField()
    type = serializers.CharField()


class NotificationUserActorSerializer(NotificationGenericActorSerializer):
    """Serializer for user notification actors."""

    gravatar_url = serializers.CharField()
    slug = serializers.CharField()


actor_serializer = PolymorphicProxySerializer(
    component_name="NotificationActor",
    # Needs to explicitly specify any supported actor types here for correct OpenAPI schema generation.
    serializers={
        "user": NotificationUserActorSerializer,
    },
    resource_type_field_name="type",
)


class NotificationSerializer(serializers.ModelSerializer[Notification]):
    """Serializer for the Notification model."""

    actor = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()
    verb = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    level = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        """Meta data for the NotificationSerializer."""

        model = Notification
        fields = (
            "id",
            "level",
            "category",
            "unread",
            "actor",
            "verb",
            "target",
            "timestamp",
            "description",
            "data",
        )

    @extend_schema_field(actor_serializer)
    def get_actor(self, obj: Notification) -> dict[str, Any] | None:
        """Get the actor representation."""
        if obj.actor:
            data: dict[str, Any] = {"id": obj.actor.pk, "str": str(obj.actor), "type": obj.actor_content_type.model}
            if isinstance(obj.actor, User):
                data["gravatar_url"] = obj.actor.gravatar_url
                data["slug"] = obj.actor.slug
            return data
        return None

    @extend_schema_field(actor_serializer)
    def get_target(self, obj: Notification) -> dict[str, Any] | None:
        """Get the target representation."""
        if obj.target and obj.target_content_type:
            data: dict[str, Any] = {"id": obj.target.pk, "str": str(obj.target), "type": obj.target_content_type.model}
            if isinstance(obj.target, User):
                data["gravatar_url"] = obj.target.gravatar_url
                data["slug"] = obj.target.slug
            return data
        return None

    def get_verb(self, obj: Notification) -> str:
        """Return the verb translated into the current request language."""
        return gettext(obj.verb)

    def get_category(self, obj: Notification) -> str:
        """Return the category label translated into the current request language."""
        return obj.get_category_display()

    def get_level(self, obj: Notification) -> str:
        """Return the level label translated into the current request language."""
        return obj.get_level_display()

    def get_description(self, obj: Notification) -> str:
        """Return the description translated and formatted into the current request language."""
        if not obj.description:
            return obj.description
        translated = gettext(obj.description)
        if "{game}" in translated and obj.data:
            lang = (get_language() or "en").split("-")[0]
            game_title = obj.data.get(f"game_title_{lang}") or obj.data.get("game_title_en", "")
            return translated.format(game=game_title)
        return translated
