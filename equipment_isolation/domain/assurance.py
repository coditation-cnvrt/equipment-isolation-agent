"""Deterministic, machine-readable explanations for assurance determinations."""
from __future__ import annotations

from typing import Any

from equipment_isolation.domain.classification import normalize_class
from equipment_isolation.domain.enums import AssuranceReasonCode, AssuranceTerminalReason

ASSURANCE_EXPLANATION_SCHEMA_VERSION = "1.0"


def build_assurance_explanation(
    *,
    assurance_status: str,
    decisive_rule: str,
    candidates: list[dict],
    evidence: dict,
    unresolved_checks: list[dict],
) -> dict[str, Any]:
    """Explain the validator result using only facts already used by validation.

    ``primary_reasons`` correspond to the decisive validator rule. Independent
    checks that would still prevent a stronger determination are kept separate as
    ``outstanding_requirements`` so one topology issue is never counted twice.
    """
    primary: list[dict[str, Any]] = []
    outstanding: list[dict[str, Any]] = []

    if decisive_rule == "no_candidates":
        primary.append(_reason(AssuranceReasonCode.NO_ISOLATION_CANDIDATES, "candidate_set"))
    elif decisive_rule == "no_barriers":
        primary.append(_reason(AssuranceReasonCode.NO_DETERMINISTIC_BARRIER, "candidate_set"))
        outstanding.extend(_boundary_reasons(evidence))
    elif decisive_rule == "missing_boundary":
        primary.extend(_boundary_reasons(evidence))
    elif decisive_rule == "manual_review":
        for candidate_id in _stable_values(evidence.get("manual_review_candidate_ids")):
            primary.append(
                _reason(
                    AssuranceReasonCode.CONDITIONAL_DEVICE_MANUAL_REVIEW,
                    f"candidate:{candidate_id}",
                    candidate_id=candidate_id,
                    required_action="confirm_conditional_device_in_field",
                )
            )
    elif decisive_rule == "unresolved_checks":
        primary.extend(_check_reasons(unresolved_checks))
    elif decisive_rule == "verification_missing":
        primary.append(
            _reason(
                AssuranceReasonCode.ZERO_ENERGY_VERIFICATION_MISSING,
                "verification_evidence",
                required_action="provide_zero_energy_verification_evidence",
            )
        )

    if decisive_rule not in {"unresolved_checks"}:
        outstanding.extend(_check_reasons(unresolved_checks))
    if decisive_rule not in {"missing_boundary", "no_barriers", "no_candidates"}:
        outstanding.extend(_boundary_reasons(evidence))

    primary = _dedupe_and_sort(primary)
    primary_keys = {item["reason_id"] for item in primary}
    outstanding = [item for item in _dedupe_and_sort(outstanding) if item["reason_id"] not in primary_keys]
    return {
        "schema_version": ASSURANCE_EXPLANATION_SCHEMA_VERSION,
        "determination": assurance_status,
        "primary_reasons": primary,
        "outstanding_requirements": outstanding,
        "summary": {
            "primary_reason_count": len(primary),
            "outstanding_requirement_count": len(outstanding),
        },
    }


def _boundary_reasons(evidence: dict) -> list[dict[str, Any]]:
    obligations = evidence.get("unresolved_isolation_obligations") or []
    reasons = []
    for obligation in obligations:
        branch_id = str(obligation.get("branch_id") or "").strip()
        source_component = str(obligation.get("source_component") or "").strip()
        subject = branch_id or f"source:{source_component or 'unknown'}"
        terminal = _terminal_summary(obligation)
        reasons.append(
            _reason(
                AssuranceReasonCode.BOUNDARY_PATH_WITHOUT_BARRIER,
                subject,
                boundary_id=branch_id or None,
                boundary_component_id=source_component or None,
                boundary_label=str(obligation.get("source_component_tag") or source_component or "").strip() or None,
                basis=str(obligation.get("basis") or "").strip() or None,
                path_node_ids=[str(value) for value in obligation.get("branch_path_node_ids") or []],
                path_node_classes=[str(value or "") for value in obligation.get("branch_path_node_classes") or []],
                encountered_devices=_encountered_devices(obligation),
                terminal=terminal,
                required_action=_boundary_action(terminal),
            )
        )
    if not reasons and int(evidence.get("missing_boundary_count") or 0) > 0:
        # Legacy/partial topology can establish an aggregate missing count without
        # identifying a branch. Preserve that uncertainty rather than inventing IDs.
        reasons.append(
            _reason(
                AssuranceReasonCode.BOUNDARY_PATH_WITHOUT_BARRIER,
                "unidentified_boundary_paths",
                boundary_count=int(evidence.get("missing_boundary_count") or 0),
                required_action="identify_uncovered_boundary_paths_and_rerun_validation",
            )
        )
    return reasons


def _encountered_devices(obligation: dict) -> list[dict[str, Any]]:
    devices = []
    for raw in obligation.get("branch_context_devices") or []:
        if not isinstance(raw, dict):
            continue
        entity_id = str(raw.get("valve_id") or raw.get("entity_id") or "").strip()
        if not entity_id:
            continue
        devices.append(
            {
                "entity_id": entity_id,
                "entity_type": str(raw.get("entity_type") or "").strip() or None,
                "entity_class": normalize_class(raw.get("entity_class")) or None,
                "tag": str(raw.get("tag") or "").strip() or None,
                "bbox": list(raw.get("bbox") or []),
                "acceptance": "context_only",
                "reason": "not_accepted_by_configured_isolation_policy",
            }
        )
    return sorted(devices, key=lambda item: (str(item.get("tag") or ""), item["entity_id"]))


def _terminal_summary(obligation: dict) -> dict[str, Any] | None:
    raw = obligation.get("terminal_node")
    if not isinstance(raw, dict) or not raw:
        path_ids = obligation.get("branch_path_node_ids") or []
        path_classes = obligation.get("branch_path_node_classes") or []
        if not path_ids:
            return None
        raw = {
            "entity_id": path_ids[-1],
            "entity_class": path_classes[-1] if path_classes else None,
        }
    entity_class = normalize_class(raw.get("entity_class"))
    partner = raw.get("partner_opc") if isinstance(raw.get("partner_opc"), dict) else {}
    partner_values = [str(partner.get(key) or "").strip() for key in ("id", "job_id")]
    if entity_class == "off_or_on_page_connector":
        if all(partner_values):
            partner_status = "resolved"
        elif any(partner_values):
            partner_status = "invalid"
        else:
            partner_status = "missing"
        terminal_reason = AssuranceTerminalReason.UNRESOLVED_OFF_PAGE_CONNECTOR.value
    elif obligation.get("basis") == "max_hops_reached":
        partner_status = "not_applicable"
        terminal_reason = AssuranceTerminalReason.TOPOLOGY_SEARCH_LIMIT_REACHED.value
    else:
        partner_status = "not_applicable"
        terminal_reason = AssuranceTerminalReason.PATH_ENDED_WITHOUT_BARRIER.value
    return {
        "entity_id": str(raw.get("entity_id") or raw.get("id") or "").strip() or None,
        "entity_type": str(raw.get("entity_type") or "").strip() or None,
        "entity_class": entity_class or None,
        "tag": str(raw.get("tag") or "").strip() or None,
        "display_text": [str(value) for value in raw.get("display_text") or [] if str(value).strip()],
        "partner_opc": {key: str(partner.get(key) or "").strip() for key in ("id", "job_id", "job_name", "opc_name")},
        "partner_mapping_status": partner_status,
        "terminal_reason": terminal_reason,
    }


def _boundary_action(terminal: dict[str, Any] | None) -> str:
    if terminal and terminal.get("terminal_reason") == AssuranceTerminalReason.UNRESOLVED_OFF_PAGE_CONNECTOR.value:
        if terminal.get("partner_mapping_status") == "resolved":
            return "traverse_partner_connector_and_rerun_validation"
        return "resolve_connector_mapping_and_rerun_validation"
    if terminal and terminal.get("terminal_reason") == AssuranceTerminalReason.TOPOLOGY_SEARCH_LIMIT_REACHED.value:
        return "extend_topology_search_and_rerun_validation"
    return "identify_or_confirm_boundary_barrier_and_rerun_validation"


def _check_reasons(checks: list[dict]) -> list[dict[str, Any]]:
    reasons = []
    for check in checks or []:
        name = str(check.get("check_name") or "unknown_check").strip()
        reasons.append(
            _reason(
                AssuranceReasonCode.EVIDENCE_CHECK_INCOMPLETE,
                f"check:{name}",
                check_name=name,
                priority=str(check.get("priority") or "").strip() or None,
                drawing_binding_status=str(check.get("drawing_binding_status") or "").strip() or None,
                evidence_targets=[target for target in check.get("evidence_targets") or [] if isinstance(target, dict)],
                completion_context=str(check.get("completion_context") or "planning"),
                blocks_plan_readiness=bool(check.get("blocks_plan_readiness", True)),
                responsible_role=str(check.get("responsible_role") or "isolation_planner"),
                method_identified=bool(check.get("method_identified")),
                loto_phase=check.get("loto_phase"),
                user_visible=bool(check.get("user_visible", True)),
                required_action="complete_required_evidence_check",
            )
        )
    return reasons


def _reason(code: AssuranceReasonCode, subject: str, **details: Any) -> dict[str, Any]:
    result = {"reason_id": f"{code.value}:{subject}", "code": code.value}
    result.update({key: value for key, value in details.items() if value is not None})
    return result


def _stable_values(values) -> list[str]:
    return sorted({str(value) for value in values or [] if value not in (None, "")})


def _dedupe_and_sort(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {str(item["reason_id"]): item for item in items}
    return [by_id[key] for key in sorted(by_id)]
