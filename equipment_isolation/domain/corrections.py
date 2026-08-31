"""Deterministic application of approved review corrections.

Corrections never patch a completed result.  They are applied to the freshly
discovered candidate set so every downstream safety rule runs again.
"""
from __future__ import annotations

from copy import deepcopy

from equipment_isolation.domain.enums import IsolationDecision
from equipment_isolation.domain.feedback import (
    SUPPORTED_FEEDBACK_TYPES,
    FeedbackEffect,
    allowed_point_feedback_types,
    feedback_definition,
    point_feedback_state,
    validate_feedback_category,
)
from equipment_isolation.domain.isolation_actions import is_installed_positive_isolation, is_operable_barrier


SUPPORTED_CORRECTION_TYPES = SUPPORTED_FEEDBACK_TYPES


def apply_approved_corrections(candidate_data: dict, corrections) -> dict:
    """Compatibility entry point for approved feedback derivation overlays."""
    return apply_approved_feedback(candidate_data, corrections)


def apply_approved_feedback(candidate_data: dict, feedback_items) -> dict:
    corrections = [dict(item) for item in (feedback_items or ())]
    if not corrections:
        return candidate_data

    result = deepcopy(candidate_data)
    candidates = list(result.get("candidates") or [])
    pool = list(result.get("_candidate_pool") or [])
    target_resolutions = list(result.get("correction_target_resolution") or [])
    applied = []

    for correction in corrections:
        kind = str(correction.get("change_type") or "")
        target_id = str(correction.get("target_id") or "")
        proposed = correction.get("proposed_change") or {}
        if kind not in SUPPORTED_CORRECTION_TYPES:
            applied.append(_coverage(correction, "failed", "Unsupported correction type."))
            continue
        try:
            category = validate_feedback_category(
                kind,
                correction.get("feedback_category"),
            )
            definition = feedback_definition(kind)
            correction["feedback_category"] = category.value
            correction.setdefault("feedback_effect", definition.effect.value)
        except ValueError as error:
            applied.append(_coverage(correction, "failed", str(error)))
            continue
        if definition.effect not in {
            FeedbackEffect.INPUT_OVERLAY,
            FeedbackEffect.MANUAL_OBSERVATION_OVERLAY,
        }:
            applied.append(
                _coverage(
                    correction,
                    "failed",
                    f"Feedback category {category.value!r} has no candidate-overlay handler.",
                )
            )
            continue

        target = _find(candidates, target_id)
        target_was_selected = target is not None
        if kind in {"add_manual_isolation_point", "mark_point_unavailable", "mark_point_available"} and target is None:
            target, identity_error = _find_addition_target(candidates, target_id)
            if identity_error:
                applied.append(_coverage(correction, "failed", identity_error))
                continue
            target_was_selected = target is not None
            if target is None:
                target, identity_error = _find_addition_target(pool, target_id)
                if identity_error:
                    applied.append(_coverage(correction, "failed", identity_error))
                    continue
                if target is not None:
                    target = deepcopy(target)
                    if kind in {"mark_point_unavailable", "mark_point_available"}:
                        target["plan_point_id"] = target_id
                    candidates.append(target)

        if target is None:
            resolution = next((item for item in target_resolutions if (
                str(item.get("change_id") or "") == str(correction.get("change_id") or "")
                or str(item.get("target_id") or "") == target_id
            )), None)
            reason = str((resolution or {}).get("reason") or "Target was not found in the fresh traversal.")
            applied.append(_coverage(correction, "failed", reason))
            continue

        if kind == "add_manual_isolation_point" and target_was_selected:
            applied.append(
                _coverage(
                    correction,
                    "failed",
                    "Point is already present in the fresh isolation candidate set.",
                )
            )
            continue
        state = point_feedback_state(target)
        availability_already_projected = (
            kind == "mark_point_unavailable" and state.value == "unavailable"
        ) or (
            kind == "mark_point_available" and state.value != "unavailable"
        )
        if availability_already_projected:
            target["correction_provenance"] = _provenance(correction)
            applied.append(
                _coverage(
                    correction,
                    "applied",
                    "Desired availability state was projected before authoritative candidate selection.",
                )
            )
            continue
        if kind != "add_manual_isolation_point" and kind not in allowed_point_feedback_types(target):
            applied.append(
                _coverage(
                    correction,
                    "failed",
                    f"Correction {kind!r} is not valid while the point is {state.value!r}.",
                )
            )
            continue

        if kind == "reject_manual_candidate":
            if not _manual_review(target):
                applied.append(_coverage(correction, "failed", "Only manual-review candidates may be rejected."))
                continue
            candidates = [item for item in candidates if str(item.get("candidate_id")) != target_id]
        elif kind in {"accept_manual_candidate", "add_manual_isolation_point"}:
            if kind == "accept_manual_candidate" and not _manual_review(target):
                applied.append(_coverage(correction, "failed", "Candidate does not require manual review."))
                continue
            _accept(target, correction)
        elif kind == "confirm_bypass":
            _accept(target, correction)
            target["required_branch_isolation"] = True
            target["manual_bypass_confirmation"] = True
            target["correction_provenance"] = _provenance(correction)
        elif kind == "correct_label":
            label = str(proposed.get("label") or "").strip()
            if not label:
                applied.append(_coverage(correction, "failed", "Corrected label is blank."))
                continue
            current_label = str(target.get("tag_number") or "").strip()
            if current_label == label:
                applied.append(
                    _coverage(correction, "failed", "Corrected label is unchanged.")
                )
                continue
            target["tag_number"] = label
            target["feedback_basis"] = category.value
            target["correction_provenance"] = _provenance(correction)
        elif kind == "mark_point_unavailable":
            target["availability_status"] = "unavailable"
            target["available_for_isolation"] = False
            target["unavailable_reason"] = str(correction.get("justification") or "").strip()
            target["correction_provenance"] = _provenance(correction)
        elif kind == "mark_point_available":
            target["availability_status"] = "available"
            target["available_for_isolation"] = True
            target.pop("unavailable_reason", None)
            target["correction_provenance"] = _provenance(correction)
        reason = (
            "Point excluded as an available isolation barrier before branch analysis and deterministic validation."
            if kind == "mark_point_unavailable"
            else "Point returned to service before branch analysis and deterministic validation."
            if kind == "mark_point_available"
            else "Applied before deterministic validation."
        )
        applied.append(_coverage(correction, "applied", reason))

    result["candidates"] = candidates
    result["total_candidates"] = len(candidates)
    result["correction_coverage"] = applied
    result.setdefault("debug", {})["approved_correction_count"] = len(corrections)
    result["debug"]["applied_correction_count"] = sum(item["status"] == "applied" for item in applied)
    return result


def _find(candidates, target_id):
    return next((item for item in candidates if str(item.get("candidate_id")) == target_id), None)


def _find_addition_target(candidates, target_id):
    """Resolve a canvas-selected HILT identity within the fresh run scope.

    Candidate ids and HILT drawing ids are separate identities.  A correction
    may carry either, but resolution must be exact and unique inside the fresh
    authoritative candidate pool; tags and labels are deliberately excluded.
    """
    matches = []
    for item in candidates:
        identities = {
            str(value).strip()
            for value in (
                item.get("candidate_id"),
                item.get("visual_node_id"),
                item.get("visual_id"),
                item.get("cnvrt_id"),
                item.get("plan_point_id"),
            )
            if value not in (None, "")
        }
        if target_id in identities:
            matches.append(item)
    if len(matches) > 1:
        return None, "Selected drawing identity matched multiple candidates in the fresh traversal."
    return (matches[0], "") if matches else (None, "")


def _manual_review(candidate):
    decision = str(candidate.get("policy_decision") or (candidate.get("classification") or {}).get("decision") or "")
    return bool(candidate.get("requires_manual_review")) or decision == IsolationDecision.CONDITIONAL_MANUAL_REVIEW.value


def _accept(candidate, correction):
    classification = dict(candidate.get("classification") or {})
    classes = classification.get("class_values") or [classification.get("raw_entity_class")]
    classification.update(
        decision=IsolationDecision.AUTOMATIC.value,
        is_barrier=any(is_operable_barrier(value) for value in classes if value),
        is_positive_isolation=any(is_installed_positive_isolation(value) for value in classes if value),
        requires_manual_review=False,
    )
    candidate["classification"] = classification
    candidate["policy_decision"] = IsolationDecision.AUTOMATIC.value
    candidate["requires_manual_review"] = False
    candidate["provenance"] = "manual"
    candidate["feedback_basis"] = "manual_observation"
    candidate["authoritative_source_update"] = False
    candidate["correction_provenance"] = _provenance(correction)


def _provenance(correction):
    return {
        "change_id": correction.get("change_id"),
        "reason": correction.get("justification"),
        "raised_by": correction.get("raised_by"),
        "approved_by": correction.get("approved_by"),
        "feedback_category": correction.get("feedback_category"),
        "feedback_effect": correction.get("feedback_effect"),
        "source_system": correction.get("source_system"),
        "source_reference": correction.get("source_reference") or {},
        "evidence": correction.get("evidence") or {},
    }


def _coverage(correction, status, reason):
    return {
        "change_id": str(correction.get("change_id") or ""),
        "feedback_category": correction.get("feedback_category"),
        "status": status,
        "reason": reason,
    }
