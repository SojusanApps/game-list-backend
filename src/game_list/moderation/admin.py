"""This module contains the admin configuration for moderation related models."""

from django.contrib import admin

from game_list.moderation.models import ModerationWarning, Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin[Report]):
    """Admin configuration for the Report model."""

    list_display = ("id", "target_type", "reported_by", "reported_user", "status", "submitted_at")
    list_filter = ("target_type", "status")
    readonly_fields = ("submitted_at",)


@admin.register(ModerationWarning)
class ModerationWarningAdmin(admin.ModelAdmin[ModerationWarning]):
    """Admin configuration for the ModerationWarning model."""

    list_display = ("id", "user", "report", "issued_by", "issued_at")
    readonly_fields = ("issued_at",)
