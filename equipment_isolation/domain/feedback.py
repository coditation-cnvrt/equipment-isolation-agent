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


class PointFeedbackState(StrEnum):
    ACCEPTED = "accepted"
    MANUAL_REVIEW = "manual_review"
    EXCLUDED = "excluded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


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

POINT_FEEDBACK_TYPES = frozenset(
    {
        "accept_manual_candidate",
        "reject_manual_candidate",
        "confirm_bypass",
        "correct_label",
        "mark_point_unavailable",
        "mark_point_available",
    }
)

_ACTIONS_BY_POINT_STATE = {
    PointFeedbackState.ACCEPTED: frozenset(
        {"correct_label", "mark_point_unavailable"}
    ),
    PointFeedbackState.MANUAL_REVIEW: frozenset(
        {
            "accept_manual_candidate",
            "reject_manual_candidate",
            "confirm_bypass",
            "correct_label",
            "mark_point_unavailable",
        }
    ),
    PointFeedbackState.EXCLUDED: frozenset(
        {"correct_label", "mark_point_unavailable"}
    ),
    PointFeedbackState.UNAVAILABLE: frozenset(
        {"correct_label", "mark_point_available"}
    ),
    PointFeedbackState.UNKNOWN: frozenset(
        {"correct_label", "mark_point_unavailable"}
    ),
}

_FEEDBACK_GROUPS = {
    "accept_manual_candidate": "selection",
    "reject_manual_candidate": "selection",
    "confirm_bypass": "selection",
    "correct_label": "label",
    "add_manual_isolation_point": "addition",
    "mark_point_unavailable": "availability",
    "mark_point_available": "availability",
}


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


def point_feedback_state(point: dict) -> PointFeedbackState:
    """Resolve the correction state of a normalized or freshly derived point."""
    if (
        point.get("available_for_isolation") is False
        or str(point.get("availability_status") or "").lower() == "unavailable"
    ):
        return PointFeedbackState.UNAVAILABLE

    explicit = str(
        point.get("feedback_state") or point.get("validation_state") or ""
    ).lower()
    explicit_states = {
        "accepted": PointFeedbackState.ACCEPTED,
        "barrier": PointFeedbackState.ACCEPTED,
        "positive": PointFeedbackState.ACCEPTED,
        "manual": PointFeedbackState.MANUAL_REVIEW,
        "manual_review": PointFeedbackState.MANUAL_REVIEW,
        "rejected": PointFeedbackState.EXCLUDED,
        "excluded": PointFeedbackState.EXCLUDED,
        "unavailable": PointFeedbackState.UNAVAILABLE,
    }
    if explicit in explicit_states:
        return explicit_states[explicit]

    classification = point.get("classification") or {}
    decision = str(
        point.get("policy_decision") or classification.get("decision") or ""
    ).lower()
    if point.get("requires_manual_review") or decision == "conditional_manual_review":
        return PointFeedbackState.MANUAL_REVIEW
    if classification.get("is_barrier") is True:
        return PointFeedbackState.ACCEPTED
    if decision in {"reject", "rejected"} or classification.get("is_barrier") is False:
        return PointFeedbackState.EXCLUDED
    return PointFeedbackState.UNKNOWN


def allowed_point_feedback_types(point: dict) -> frozenset[str]:
    return _ACTIONS_BY_POINT_STATE[point_feedback_state(point)]


def feedback_transition_group(feedback_type: str) -> str:
    try:
        return _FEEDBACK_GROUPS[str(feedback_type)]
    except KeyError:
        raise ValueError(f"Unsupported feedback type: {feedback_type}") from None
