"""Tests for custom exceptions."""

from my_game_list.my_game_list.exceptions import SerializerValidationDetailError


def test_serializer_validation_detail_error_carries_a_fixed_message() -> None:
    """The error always carries the same descriptive message, regardless of what triggered it."""
    error = SerializerValidationDetailError()

    assert str(error) == "Validation error detail returns wrong structure."
