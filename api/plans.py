"""Application helpers for stable isolation plans and immutable versions."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from agent.session import jsonable


@dataclass
class PlanDomainError(Exception):
    kind: str
    message: str
    status_code: int
    context: dict[str, Any] | None = None

    def detail(self) -> dict[str, Any]:
        return {"kind": self.kind, "message": self.message, **(self.context or {})}


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def model_fingerprint(runner: str, agent: dict[str, Any] | None) -> dict[str, Any]:
    agent = agent or {}
    return {
        "runner": runner,
        "model": agent.get("model"),
        "models_used": agent.get("models_used") or [],
        "build_revision": os.environ.get("EIA_BUILD_REVISION", "").strip(),
        "degraded": bool(agent.get("orchestration_error")),
    }


def derivation_status(agent: dict[str, Any] | None) -> str:
    return "completed_degraded" if (agent or {}).get("orchestration_error") else "completed"


def assurance_status(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None
    data = result.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        return None
    value = data[0].get("assurance_status")
    return str(value) if value not in {None, ""} else None


def validate_promotable_result(result: Any) -> None:
    if assurance_status(result) is None:
        raise PlanDomainError(
            kind="invalid_run_result",
            message="The succeeded run does not contain a usable isolation plan result.",
            status_code=409,
        )


def normalized_plan_content(request: dict, result: dict) -> dict:
    """Build the immutable plan-owned projection used by reads and diffs."""
    validate_promotable_result(result)
    data = (result.get("data") or [{}])[0]
    points = [_normalized_point(item) for item in (data.get("isolation_points") or [])]
    branches_by_key: dict[str, dict] = {}
    for point in points:
        for membership in point["branch_memberships"]:
            key = membership["branch_key"]
            branch = branches_by_key.setdefault(
                key,
                {
                    "key": key,
                    "path_node_ids": membership.get("path_node_ids") or [],
                    "point_keys": [],
                    "unavailable_point_keys": [],
                },
            )
            if not branch["path_node_ids"] and membership.get("path_node_ids"):
                branch["path_node_ids"] = membership["path_node_ids"]
            if point.get("available_for_isolation") is False or point.get("availability_status") == "unavailable":
                branch["unavailable_point_keys"].append(point["key"])
            else:
                branch["point_keys"].append(point["key"])
    branches = []
    for branch in branches_by_key.values():
        branch["point_keys"] = sorted(set(branch["point_keys"]))
        branch["unavailable_point_keys"] = sorted(set(branch["unavailable_point_keys"]))
        branch["coverage_status"] = "covered" if branch["point_keys"] else "unresolved"
        branch["topology_signature"] = canonical_hash(
            branch.get("path_node_ids") or branch["point_keys"] or branch["unavailable_point_keys"]
        )
        branches.append(branch)

    loto = data.get("loto_procedure") or {}
    raw_steps = loto.get("ordered_steps") or loto.get("phases") or []
    steps = []
    for index, item in enumerate(raw_steps, 1):
        if not isinstance(item, dict):
            continue
        key = _normalized_step_key(item, index)
        steps.append({"key": key, "sequence_no": index, **jsonable(item)})

    readiness = data.get("plan_readiness") or {}
    validation = data.get("isolation_validation") or {}
    explanation = validation.get("assurance_explanation") or {}
    finding_rows = []
    groups = (
        readiness.get("planning_blockers") or [],
        readiness.get("pre_job_review_items") or [],
        explanation.get("primary_reasons") or [],
        explanation.get("outstanding_requirements") or [],
    )
    for group in groups:
        for item in group:
            if not isinstance(item, dict):
                continue
            key = str(item.get("requirement_id") or item.get("reason_id") or canonical_hash(item))
            if any(existing["key"] == key for existing in finding_rows):
                continue
            finding_rows.append({"key": key, "blocks_authorisation": bool(item.get("blocks_plan_readiness", True)), **jsonable(item)})

    selected = request.get("selected_asset") or {}
    target = data.get("target_identity") or selected
    return {
        "schema_version": "1.0",
        "context": {key: request.get(key) for key in ("cnvrt_project_id", "collection_id", "unigraph_project_id", "job_id", "job_name", "collection_name")},
        "selected_asset": selected,
        "target_identity": target,
        "work_scope": request.get("work_scope") or {},
        "assurance_status": data.get("assurance_status"),
        "points": sorted(points, key=lambda item: item["key"]),
        "branches": sorted(branches, key=lambda item: item["key"]),
        "steps": steps,
        "findings": sorted(finding_rows, key=lambda item: item["key"]),
        "correction_coverage": data.get("correction_coverage") or (result.get("debug") or {}).get("correction_coverage") or [],
    }


def plan_content_diff(before: dict | None, after: dict) -> dict:
    sections = {}
    summary = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0, "safety_significant": 0}
    before = before or {}
    for section in ("branches", "points", "steps", "findings"):
        left = {str(item.get("key")): item for item in (before.get(section) or [])}
        right = {str(item.get("key")): item for item in (after.get(section) or [])}
        bucket = {"added": [], "removed": [], "changed": [], "unchanged": []}
        for key in sorted(left.keys() | right.keys()):
            old, new = left.get(key), right.get(key)
            if old is None:
                kind = "added"
            elif new is None:
                kind = "removed"
            elif canonical_hash(old) != canonical_hash(new):
                kind = "changed"
            else:
                kind = "unchanged"
            significant = section in {"branches", "points", "steps"} and kind != "unchanged"
            bucket[kind].append({"key": key, "before": old, "after": new, "safety_significant": significant})
            summary[kind] += 1
            summary["safety_significant"] += int(significant)
        sections[section] = bucket
    if canonical_hash(before.get("work_scope") or {}) != canonical_hash(after.get("work_scope") or {}):
        summary["changed"] += 1
        summary["safety_significant"] += 1
        sections["work_scope"] = {"added": [], "removed": [], "unchanged": [], "changed": [{
            "key": "work_scope", "before": before.get("work_scope"), "after": after.get("work_scope"), "safety_significant": True,
        }]}
    return {"sections": sections, "summary": summary}


def _normalized_step_key(item: dict, index: int) -> str:
    explicit = item.get("step_id") or item.get("id")
    if explicit not in (None, ""):
        return str(explicit)
    target = item.get("target") or {}
    target_id = (
        target.get("candidate_id")
        or target.get("drawing_entity_id")
        or target.get("instrument_id")
        or item.get("device_uuid")
        or item.get("instrument_id")
        or item.get("secondary_context_source")
    )
    phase = item.get("phase") or "unknown"
    step_type = item.get("step_type")
    if not step_type:
        if item.get("device_uuid"):
            step_type = "operate_isolation" if phase == 3 else "apply_lock_tag" if phase == 4 else "device_action"
        elif item.get("instrument_id"):
            step_type = "instrument_check"
        elif item.get("field_gap"):
            step_type = "field_gap"
        else:
            step_type = "legacy_action"
    if target_id not in (None, ""):
        return f"phase:{phase}:{step_type}:{target_id}"
    action = str(item.get("action") or item.get("title") or item.get("sequence") or index)
    return f"phase:{phase}:{step_type}:{canonical_hash(action)[:12]}"


def _normalized_point(item: dict) -> dict:
    key = str(item.get("uuid") or item.get("drawing_entity_id") or item.get("equipment_id") or canonical_hash(item))
    memberships = _branch_memberships(item)
    return {
        **jsonable(item),
        "key": key,
        "external_id": key,
        "drawing_entity_id": item.get("drawing_entity_id"),
        "tag": item.get("tag_number") or item.get("equipment_id") or key,
        "asset_class": item.get("entity_class") or "",
        "branch_key": memberships[0]["branch_key"],
        "branch_keys": [membership["branch_key"] for membership in memberships],
        "branch_memberships": memberships,
        "branch_path_node_ids": item.get("branch_path_node_ids") or [],
        "provenance": item.get("provenance") or ("manual" if item.get("correction_provenance") else "derived"),
    }


def _branch_memberships(item: dict) -> list[dict]:
    memberships: dict[str, dict] = {}

    def add(source: dict, *, primary: bool = False) -> None:
        branch_key = str(
            source.get("branch_id")
            or source.get("source_component_id")
            or source.get("source_component")
            or source.get("source_component_tag")
            or "unassigned"
        )
        path_node_ids = source.get("branch_path_node_ids") or source.get("path_node_ids") or []
        existing = memberships.get(branch_key)
        if existing is None:
            memberships[branch_key] = {
                "branch_key": branch_key,
                "path_node_ids": jsonable(path_node_ids),
                "path_order": int(source.get("path_order") or 0),
                "primary": primary,
            }
        elif not existing["path_node_ids"] and path_node_ids:
            existing["path_node_ids"] = jsonable(path_node_ids)
        if primary:
            existing = memberships[branch_key]
            existing["primary"] = True

    add(item, primary=True)
    for path in item.get("source_paths") or []:
        if isinstance(path, dict):
            add(path)
    return list(memberships.values())
