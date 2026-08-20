"""This module contains the serializers for moderation related data."""

from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, Self

from django.db import transaction
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from my_game_list.moderation.models import Report, ReportTargetType, is_target_already_moderated
from my_game_list.users.models import User
from my_game_list.users.serializers import UserSimpleSerializer

if TYPE_CHECKING:
    from collections.abc import Callable


class _TargetSpec(NamedTuple):
    """How to handle one target_type at create time: which attrs key holds the target, and how to read it."""

    field: str
    get_owner: Callable[[Any], Any]
    get_value: Callable[[Any], str]


_TARGET_SPECS: dict[str, _TargetSpec] = {
    ReportTargetType.REVIEW: _TargetSpec("target_review", lambda t: t.user, lambda t: t.review),
    ReportTargetType.GAME_LIST_NOTE: _TargetSpec("target_game_list", lambda t: t.user, lambda t: t.description),
    ReportTargetType.TRANSLATION_SUGGESTION: _TargetSpec(
        "target_translation_suggestion",
        lambda t: t.submitted_by,
        lambda t: t.proposed_value,
    ),
    ReportTargetType.COLLECTION: _TargetSpec(
        "target_collection",
        lambda t: t.user,
        lambda t: f"name: {t.name}\ndescription: {t.description}",
    ),
    ReportTargetType.COLLECTION_ITEM_NOTE: _TargetSpec(
        "target_collection_item",
        lambda t: t.added_by,
        lambda t: t.description,
    ),
    # AVATAR/USERNAME target a User directly - no content row, no target FK. The "target" the
    # client supplies IS the reported user, so field points at reported_user itself and get_owner
    # is the identity function.
    ReportTargetType.AVATAR: _TargetSpec("reported_user", lambda t: t, lambda _t: ""),
    ReportTargetType.USERNAME: _TargetSpec("reported_user", lambda t: t, lambda t: t.username),
}


class ReportSerializer(serializers.ModelSerializer[Report]):
    """A serializer for reading reports."""

    reported_by = UserSimpleSerializer(read_only=True)
    reported_user = UserSimpleSerializer(read_only=True)
    reviewed_by = UserSimpleSerializer(read_only=True)

    class Meta:
        """Meta data for the report serializer."""

        model = Report
        fields = (
            "id",
            "target_type",
            "target_review",
            "target_translation_suggestion",
            "target_game_list",
            "target_collection",
            "target_collection_item",
            "reported_by",
            "reported_user",
            "reported_value",
            "reason",
            "source",
            "status",
            "submitted_at",
            "reviewed_by",
            "reviewed_at",
            "rejection_reason",
        )
        read_only_fields = tuple(f for f in fields if f not in {"reported_by", "reported_user", "reviewed_by"})


class ReportCreateSerializer(serializers.ModelSerializer[Report]):
    """A serializer for submitting a new report."""

    # Writable, but only meaningful for AVATAR/USERNAME (target a User directly, no content row to
    # derive an owner from). For content-based target_types this is ignored - create() always
    # derives reported_user from the live content, never from client input.
    reported_user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), required=False)

    class Meta:
        """Meta data for the report create serializer."""

        model = Report
        fields = (
            "id",
            "target_type",
            "target_review",
            "target_translation_suggestion",
            "target_game_list",
            "target_collection",
            "target_collection_item",
            "reason",
            "reported_by",
            "reported_user",
            "reported_value",
            "status",
            "submitted_at",
        )
        read_only_fields: ClassVar[tuple[str, ...]] = (
            "id",
            "reported_by",
            "reported_value",
            "status",
            "submitted_at",
        )

    def validate(self: Self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Validate the target reference for the chosen target_type and reject self-reports/duplicates."""
        target_type: str | None = attrs.get("target_type")
        request = self.context["request"]

        spec = _TARGET_SPECS.get(target_type) if target_type is not None else None
        if spec is None:
            message = _("Reporting a %(target_type)s is not yet supported.") % {"target_type": target_type}
            raise serializers.ValidationError({"target_type": message})

        target = attrs.get(spec.field)
        if target is None:
            message = _("This field is required for %(target_type)s reports.") % {"target_type": target_type}
            raise serializers.ValidationError({spec.field: message})

        owner = spec.get_owner(target)
        if owner is None:
            no_user_message = _("This item has no reportable user (its adding user was deleted).")
            raise serializers.ValidationError({"non_field_errors": [no_user_message]})

        if owner.id == request.user.id:
            own_content_message = _("You cannot report your own content.")
            raise serializers.ValidationError({"non_field_errors": [own_content_message]})

        if Report.objects.filter(
            reported_by=request.user,
            status=Report.Status.PENDING,
            target_type=target_type,
            **{spec.field: target},
        ).exists():
            duplicate_report_message = _("You already have a pending report for this.")
            raise serializers.ValidationError({"non_field_errors": [duplicate_report_message]})

        return attrs

    def create(self: Self, validated_data: dict[str, Any]) -> Report:
        """Create a report, deriving reported_user/reported_value server-side from the live target."""
        request = self.context["request"]
        target_type = validated_data["target_type"]
        spec = _TARGET_SPECS[target_type]
        target = validated_data[spec.field]
        kwargs: dict[str, Any] = {
            "target_type": target_type,
            "reason": validated_data.get("reason", ""),
            "reported_by": request.user,
            "reported_user": spec.get_owner(target),
            "reported_value": spec.get_value(target),
        }
        # spec.field is "reported_user" for AVATAR/USERNAME, already set above with the same value.
        kwargs.setdefault(spec.field, target)

        return Report.objects.create(**kwargs)


class ReportDirectModerateSerializer(ReportCreateSerializer):
    """A serializer for an admin directly moderating a target, bypassing the pending queue."""

    def validate(self: Self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Run the base target/self-report checks, then refuse staff targets and already-moderated targets."""
        attrs = super().validate(attrs)
        target_type = attrs["target_type"]
        spec = _TARGET_SPECS[target_type]
        target = attrs[spec.field]
        owner = spec.get_owner(target)

        if owner.is_staff:
            message = _("This admin action cannot target a staff user.")
            raise serializers.ValidationError({"non_field_errors": [message]})

        if is_target_already_moderated(target_type, target):
            message = _("This has already been moderated.")
            raise serializers.ValidationError({"non_field_errors": [message]})

        return attrs

    def create(self: Self, validated_data: dict[str, Any]) -> Report:
        """Create a Report authored by the admin and immediately accept it, sweeping duplicate pending reports.

        Any other still-pending Report on the exact same target is accepted alongside it (attributed to
        the same admin) but does not itself issue a Warning - a target is warned once per moderation event.
        """
        request = self.context["request"]
        target_type = validated_data["target_type"]
        spec = _TARGET_SPECS[target_type]
        target = validated_data[spec.field]
        owner = spec.get_owner(target)

        kwargs: dict[str, Any] = {
            "target_type": target_type,
            "reason": validated_data.get("reason", ""),
            "reported_by": request.user,
            "reported_user": owner,
            "reported_value": spec.get_value(target),
            "source": Report.Source.ADMIN_DIRECT,
        }
        kwargs.setdefault(spec.field, target)

        with transaction.atomic():
            report = Report.objects.create(**kwargs)
            report.accept(request.user, issue_warning=True)

            sibling_filter = {"reported_user": owner} if spec.field == "reported_user" else {spec.field: target}
            siblings = Report.objects.filter(
                status=Report.Status.PENDING,
                target_type=target_type,
                **sibling_filter,
            ).exclude(pk=report.pk)
            for sibling in siblings:
                sibling.accept(request.user, issue_warning=False)

        return report
