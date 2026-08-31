from equipment_isolation.domain.assurance import build_assurance_explanation
from equipment_isolation.domain.enums import AssuranceStatus
from equipment_isolation.domain.plan_readiness import build_plan_readiness


MISSING_BY_CHECK = {
    "find_bypass_paths": "Bypass or alternate-route evidence check is required but has not been completed by this local deterministic runner.",
    "find_blinds_spades_flanges": "Positive isolation evidence check is required but has not been completed by this local deterministic runner.",
    "find_bleeds_vents_drains": "Bleed, vent, or drain evidence check is required but has not been completed by this local deterministic runner.",
    "find_pressure_indicators": "Pressure gauge, pressure indicator, or test-point evidence check is required but has not been completed by this local deterministic runner.",
    "confirm_zero_pressure": "A located pressure indicator must record zero gauge pressure (or the site-approved safe threshold), remain stable for the required hold period, and show no reaccumulation.",
}


def validate(planner_data):
    candidates = planner_data.get("candidates", []) or []
    evidence = planner_data.get("evidence_state") or {}
    missing = list(evidence.get("missing_evidence") or planner_data.get("missing_evidence") or [])
    unresolved = []
    for check in planner_data.get("required_evidence_checks") or []:
        check_name = check.get("check_name")
        if check_name in MISSING_BY_CHECK and check.get("status") not in {"completed", "resolved", "not_applicable"}:
            unresolved.append(check)
            if MISSING_BY_CHECK[check_name] not in missing:
                missing.append(MISSING_BY_CHECK[check_name])

    missing_boundary_count = evidence.get("missing_boundary_count")
    barrier_ids = evidence.get("barrier_candidate_ids") or []
    positive_ids = evidence.get("positive_candidate_ids") or []
    verification_ids = evidence.get("verification_candidate_ids") or []
    manual_review_ids = evidence.get("manual_review_candidate_ids") or []
    unavailable_ids = evidence.get("unavailable_candidate_ids") or []

    if not candidates:
        status = AssuranceStatus.NOT_ISOLATED
        decisive_rule = "no_candidates"
        rationale = "No isolation candidates were found."
    elif not barrier_ids:
        status = AssuranceStatus.NOT_ISOLATED
        decisive_rule = "no_barriers"
        rationale = "No selected candidate has deterministic isolation barrier evidence."
    elif missing_boundary_count and missing_boundary_count > 0:
        status = AssuranceStatus.NOT_ISOLATED
        decisive_rule = "missing_boundary"
        rationale = "At least one equipment boundary path has no selected isolation barrier."
    elif manual_review_ids:
        status = AssuranceStatus.PROVISIONAL_UNPROVEN_ISOLATION
        decisive_rule = "manual_review"
        rationale = "Selected barriers include conditional isolation devices that require manual review before acceptance."
    elif unresolved:
        status = AssuranceStatus.PROVISIONAL_UNPROVEN_ISOLATION
        decisive_rule = "unresolved_checks"
        rationale = "Selected barriers exist, but safety-critical evidence checks remain unresolved."
    elif positive_ids and verification_ids:
        status = AssuranceStatus.COMPLETE_POSITIVE_ISOLATION
        decisive_rule = "complete_positive"
        rationale = "Every known boundary path has a selected barrier, positive isolation evidence exists, and verification evidence exists."
    elif verification_ids:
        status = AssuranceStatus.COMPLETE_PROVEN_ISOLATION
        decisive_rule = "complete_proven"
        rationale = "Every known boundary path has a selected barrier and verification evidence exists, but positive isolation evidence was not found."
    else:
        status = AssuranceStatus.PROVISIONAL_UNPROVEN_ISOLATION
        decisive_rule = "verification_missing"
        rationale = "Selected barriers exist for known boundary paths, but proof of zero or safe energy was not found."

    assurance_explanation = build_assurance_explanation(
        assurance_status=status.value,
        decisive_rule=decisive_rule,
        candidates=candidates,
        evidence=evidence,
        unresolved_checks=unresolved,
    )
    plan_readiness = build_plan_readiness(
        assurance_status=status.value,
        assurance_explanation=assurance_explanation,
        unresolved_checks=unresolved,
    )
    validation = {
        "code_version": "local_validator_2026-08-18_v5",
        "assurance_status": status.value,
        "rationale": rationale,
        "assurance_explanation": assurance_explanation,
        "plan_readiness": plan_readiness,
        "terminal": status in {
            AssuranceStatus.COMPLETE_POSITIVE_ISOLATION,
            AssuranceStatus.COMPLETE_PROVEN_ISOLATION,
            AssuranceStatus.NOT_ISOLATED,
            AssuranceStatus.INSUFFICIENT_DATA,
        },
        "candidate_count": len(candidates),
        "expected_boundary_count": evidence.get("expected_boundary_count"),
        "covered_boundary_source_count": evidence.get("covered_boundary_source_count"),
        "missing_boundary_count": missing_boundary_count,
        "unselected_boundary_sources": evidence.get("unselected_boundary_sources") or [],
        "boundary_context_sources": evidence.get("boundary_context_sources") or evidence.get("context_instruments") or [],
        "context_instruments": evidence.get("context_instruments") or [],
        "isolation_obligations": evidence.get("isolation_obligations") or {},
        "unresolved_isolation_obligations": evidence.get("unresolved_isolation_obligations") or [],
        "relief_context_obligations": evidence.get("relief_context_obligations") or [],
        "barrier_candidate_ids": barrier_ids,
        "positive_candidate_ids": positive_ids,
        "verification_candidate_ids": verification_ids,
        "manual_review_candidate_ids": manual_review_ids,
        "unavailable_candidate_ids": unavailable_ids,
        "bypass_candidate_ids": evidence.get("bypass_candidate_ids") or [],
        "unresolved_bbox_candidate_ids": evidence.get("unresolved_bbox_candidate_ids") or [],
        "unresolved_evidence_checks": unresolved,
        "missing_evidence": missing,
    }
    debug = dict(planner_data.get("debug", {}) or {})
    debug.update(
        {
            "assurance_status": status,
            "validator_terminal": validation["terminal"],
            "validator_unresolved_evidence_check_count": len(unresolved),
            "validator_manual_review_candidate_count": len(manual_review_ids),
            "validator_missing_evidence_count": len(missing),
            "validator_primary_reason_count": assurance_explanation["summary"]["primary_reason_count"],
            "validator_outstanding_requirement_count": assurance_explanation["summary"]["outstanding_requirement_count"],
        }
    )
    debug["assurance_status"] = status.value
    return {
        **planner_data,
        "debug": debug,
        "missing_evidence": missing,
        "isolation_validation": validation,
        "plan_readiness": plan_readiness,
        "assurance_status": status.value,
    }
