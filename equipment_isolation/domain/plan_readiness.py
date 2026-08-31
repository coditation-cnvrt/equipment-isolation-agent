"""Deterministic advisory-plan readiness, separate from isolation assurance.

Plan readiness answers whether a usable field-review plan was generated. It does
not assert that any device was operated, locked, drained, or verified. The
validator remains the exclusive owner of ``assurance_status``.
"""
from __future__ import annotations

from typing import Any

PLAN_READINESS_SCHEMA_VERSION = "1.0"

_HARD_REASON_CODES = {
    "no_isolation_candidates",
    "no_deterministic_barrier",
    "boundary_path_without_barrier",
    "zero_energy_verification_missing",
}


def build_plan_readiness(*, assurance_status: str, assurance_explanation: dict, unresolved_checks: list[dict]) -> dict[str, Any]:
    reasons = list(assurance_explanation.get("primary_reasons") or []) + list(
        assurance_explanation.get("outstanding_requirements") or []
    )
    checks_by_name = {
        str(check.get("check_name") or ""): check
        for check in unresolved_checks or []
        if isinstance(check, dict) and check.get("check_name")
    }

    blockers: list[dict] = []
    pre_job: list[dict] = []
    field_holds: list[dict] = []
    seen = set()

    for reason in reasons:
        reason_id = str(reason.get("reason_id") or "")
        if not reason_id or reason_id in seen:
            continue
        seen.add(reason_id)
        code = str(reason.get("code") or "")
        check = checks_by_name.get(str(reason.get("check_name") or ""))
        if check:
            if not check.get("user_visible", True):
                continue
            item = _check_item(reason, check)
            context = item["completion_context"]
            if item["blocks_plan_readiness"]:
                blockers.append(item)
            elif context == "field_execution":
                field_holds.append(item)
            elif context == "pre_job_review":
                pre_job.append(item)
            continue
        if code in _HARD_REASON_CODES:
            blockers.append(_reason_item(reason))
        elif code == "conditional_device_manual_review":
            pre_job.append(
                {
                    **_reason_item(reason),
                    "completion_context": "pre_job_review",
                    "blocks_plan_readiness": False,
                    "responsible_role": "authorized_field_personnel",
                    "method_identified": True,
                }
            )

    blockers = _stable(blockers)
    pre_job = _stable(pre_job)
    field_holds = sorted(_stable(field_holds), key=lambda item: (int(item.get("loto_phase") or 99), item["requirement_id"]))

    if assurance_status == "insufficient_data":
        status = "insufficient_data"
        planning_complete = False
        rationale = "Available topology and evidence are insufficient to produce a field-review plan."
    elif blockers:
        status = "incomplete"
        planning_complete = False
        rationale = "Planning blockers remain; the advisory plan is not ready for field review."
    else:
        status = "ready_for_field_review"
        planning_complete = True
        rationale = (
            "All known planning blockers are resolved and required field actions are identified. "
            "Field review and execution-stage verification are still required."
        )

    return {
        "schema_version": PLAN_READINESS_SCHEMA_VERSION,
        "status": status,
        "planning_complete": planning_complete,
        "advisory_only": True,
        "field_authorization": False,
        "rationale": rationale,
        "planning_blockers": blockers,
        "pre_job_review_items": pre_job,
        "field_execution_hold_points": field_holds,
        "summary": {
            "planning_blocker_count": len(blockers),
            "pre_job_review_count": len(pre_job),
            "field_hold_point_count": len(field_holds),
        },
    }


def _check_item(reason: dict, check: dict) -> dict[str, Any]:
    return {
        "requirement_id": str(reason.get("reason_id") or f"check:{check.get('check_name')}"),
        "reason_id": str(reason.get("reason_id") or ""),
        "code": str(reason.get("code") or "evidence_check_incomplete"),
        "check_name": str(check.get("check_name") or ""),
        "instruction": str(check.get("reason") or "").strip(),
        "priority": str(check.get("priority") or "").strip() or None,
        "completion_context": str(check.get("completion_context") or "planning"),
        "blocks_plan_readiness": bool(check.get("blocks_plan_readiness", True)),
        "responsible_role": str(check.get("responsible_role") or "isolation_planner"),
        "method_identified": bool(check.get("method_identified")),
        "drawing_binding_status": str(check.get("drawing_binding_status") or "").strip() or None,
        "evidence_targets": [target for target in check.get("evidence_targets") or [] if isinstance(target, dict)],
        **({"loto_phase": int(check["loto_phase"])} if check.get("loto_phase") is not None else {}),
    }


def _reason_item(reason: dict) -> dict[str, Any]:
    return {
        **reason,
        "requirement_id": str(reason.get("reason_id") or reason.get("code") or "planning-blocker"),
        "completion_context": "planning",
        "blocks_plan_readiness": True,
        "responsible_role": "isolation_planner",
        "method_identified": False,
    }


def _stable(items: list[dict]) -> list[dict]:
    by_id = {str(item["requirement_id"]): item for item in items}
    return [by_id[key] for key in sorted(by_id)]
