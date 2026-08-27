"""Typed isolation-plan feedback definitions and deterministic dispatch policy.

Feedback records are governance inputs.  Only feedback types registered with a
derivation effect may be translated into an overlay consumed by the safety
pipeline.  Unsupported future categories remain representable without gaining
an accidental code path into validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FeedbackCategory(StrEnum):
    INPUT_CORRECTION = "input_correction"
    REQUIREMENT_DEVIATION = "requirement_deviation"
    MANUAL_OBSERVATION = "manual_observation"
    EXECUTION_FAILURE = "execution_failure"


class FeedbackEffect(StrEnum):
    INPUT_OVERLAY = "input_overlay"
    MANUAL_OBSERVATION_OVERLAY = "manual_observation_overlay"
    ATTACH_DEVIATION = "attach_deviation"
    EXECUTION_STATE_CHANGE = "execution_state_change"


@dataclass(frozen=True)
class FeedbackDefinition:
    category: FeedbackCategory
    effect: FeedbackEffect
    derivation_supported: bool


FEEDBACK_DEFINITIONS = {
    "correct_label": FeedbackDefinition(
        FeedbackCategory.INPUT_CORRECTION,
        FeedbackEffect.INPUT_OVERLAY,
        True,
    ),
    "mark_point_unavailable": FeedbackDefinition(
        FeedbackCategory.INPUT_CORRECTION,
        FeedbackEffect.INPUT_OVERLAY,
        True,
    ),
    "mark_point_available": FeedbackDefinition(
        FeedbackCategory.INPUT_CORRECTION,
        FeedbackEffect.INPUT_OVERLAY,
        True,
    ),
    "accept_manual_candidate": FeedbackDefinition(
        FeedbackCategory.MANUAL_OBSERVATION,
        FeedbackEffect.MANUAL_OBSERVATION_OVERLAY,
        True,
    ),
    "reject_manual_candidate": FeedbackDefinition(
        FeedbackCategory.MANUAL_OBSERVATION,
        FeedbackEffect.MANUAL_OBSERVATION_OVERLAY,
        True,
    ),
    "confirm_bypass": FeedbackDefinition(
        FeedbackCategory.MANUAL_OBSERVATION,
        FeedbackEffect.MANUAL_OBSERVATION_OVERLAY,
        True,
    ),
    "add_manual_isolation_point": FeedbackDefinition(
        FeedbackCategory.MANUAL_OBSERVATION,
        FeedbackEffect.MANUAL_OBSERVATION_OVERLAY,
        True,
    ),
}

SUPPORTED_FEEDBACK_TYPES = frozenset(FEEDBACK_DEFINITIONS)


def feedback_definition(feedback_type: str) -> FeedbackDefinition:
    """Return the registered definition or reject unsupported behavior."""
    try:
        return FEEDBACK_DEFINITIONS[str(feedback_type)]
    except KeyError:
        raise ValueError(f"Unsupported feedback type: {feedback_type}") from None


def feedback_category(feedback_type: str) -> FeedbackCategory:
    return feedback_definition(feedback_type).category


def validate_feedback_category(feedback_type: str, category: str | None) -> FeedbackCategory:
    expected = feedback_category(feedback_type)
    if category is not None and str(category) != expected.value:
        raise ValueError(
            f"Feedback type {feedback_type!r} belongs to category {expected.value!r}, "
            f"not {category!r}."
        )
    return expected


def derivation_effect(feedback_type: str) -> FeedbackEffect:
    definition = feedback_definition(feedback_type)
    if not definition.derivation_supported:
        raise ValueError(f"Feedback type {feedback_type!r} cannot affect a derivation.")
    return definition.effect
