"""Versioned, intrinsic governance policy for source-data defects."""
from __future__ import annotations

import hashlib
import json
from typing import Any


POLICY_VERSION = "source-defect-policy/1.0"
OPEN_STATES = frozenset({"reported", "confirmed", "remediation_recorded"})
MATERIAL_STATES = frozenset({"confirmed", "remediation_recorded"})
TERMINAL_STATES = frozenset({"resolved", "rejected", "withdrawn"})
ANCHOR_TYPES = frozenset({"entity", "link", "point", "region"})

# This catalogue is application policy, deliberately not runtime configuration.
_CATALOGUE: dict[str, dict[str, Any]] = {
    "missing_device": {
        "severity": "blocking", "anchors": ["point", "region"], "matching": "drawing",
        "required_report_facts": ["expected_device"],
    },
    "extra_device": {
        "severity": "blocking", "anchors": ["entity"], "matching": "exact_then_unknown_fallback",
        "required_report_facts": ["observed_device"],
    },
    "incorrect_device_type": {
        "severity": "blocking", "anchors": ["entity"], "matching": "exact_then_unknown_fallback",
        "required_report_facts": ["observed_type", "expected_type"],
    },
    "incorrect_symbol": {
        "severity": "advisory", "anchors": ["entity", "region"], "matching": "exact_then_unknown_fallback",
        "required_report_facts": ["observed_symbol", "expected_symbol"],
    },
    "incorrect_label": {
        "severity": "blocking", "anchors": ["entity", "link"], "matching": "exact_then_unknown_fallback",
        "required_report_facts": ["observed_label", "expected_label"],
    },
    "incorrect_attribute": {
        "severity": "blocking", "anchors": ["entity", "link"], "matching": "exact_then_unknown_fallback",
        "required_report_facts": ["attribute", "observed_value", "expected_value"],
        "fallback": "fail_closed_when_dependency_unknown",
    },
    "missing_connection": {
        "severity": "blocking", "anchors": ["point", "region"], "matching": "drawing",
        "required_report_facts": ["expected_endpoints"],
    },
    "phantom_connection": {
        "severity": "blocking", "anchors": ["link"], "matching": "exact_then_unknown_fallback",
        "required_report_facts": ["observed_endpoints"],
    },
    "incorrect_connection": {
        "severity": "blocking", "anchors": ["link"], "matching": "exact_then_unknown_fallback",
        "required_report_facts": ["observed_endpoints", "expected_endpoints"],
    },
    "off_page_connector_mismatch": {
        "severity": "blocking", "anchors": ["entity", "link"], "matching": "drawing",
        "required_report_facts": ["connector_label", "counterpart_reference"],
    },
    "source_revision_mismatch": {
        "severity": "blocking", "anchors": ["region"], "matching": "source_revision",
        "required_report_facts": ["observed_revision", "expected_revision"],
    },
    "other": {
        "severity": "warning", "anchors": ["entity", "link", "point", "region"], "matching": "drawing",
        "required_report_facts": ["observed_issue"], "confirmation_requires_reclassification": True,
    },
}

DEFECT_CATEGORIES = frozenset(_CATALOGUE)


def _hash(value: dict[str, Any]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def policy_snapshot(category: str) -> dict[str, Any]:
    """Return the complete immutable category policy stored with each event."""

    if category not in _CATALOGUE:
        raise ValueError(f"Unsupported source-data defect category: {category}")
    snapshot = {
        "policy_version": POLICY_VERSION,
        "category": category,
        **_CATALOGUE[category],
        "required_report_evidence_refs": 1,
        "transition_requirements": {
            "confirm": {"evidence_refs": 1},
            "remediation_recorded": {
                "evidence_refs": 1,
                "remediation_facts": ["summary", "reference"],
            },
            "resolve": {"evidence_refs": 1},
            "reject": {}, "withdraw": {}, "reopen": {},
            "reclassified": {"evidence_refs": 1},
            "commented": {}, "evidence_added": {"evidence_refs": 1},
            "claimed": {}, "released": {},
        },
        "material_states": sorted(MATERIAL_STATES),
        "affects": ["governance_readiness", "freshness"],
        "excluded_effects": ["assurance_status", "topology", "candidates", "loto"],
    }
    return {**snapshot, "policy_hash": _hash(snapshot)}


def policy_catalogue() -> dict[str, Any]:
    categories = {key: policy_snapshot(key) for key in sorted(_CATALOGUE)}
    payload = {"policy_version": POLICY_VERSION, "categories": categories}
    return {**payload, "catalogue_hash": _hash(payload)}


def validate_report(category: str, anchor_type: str, facts: dict, evidence_refs: list[str]) -> None:
    policy = policy_snapshot(category)
    if anchor_type not in policy["anchors"]:
        allowed = ", ".join(policy["anchors"])
        raise ValueError(f"{category} requires one of these anchor types: {allowed}")
    missing = [key for key in policy["required_report_facts"] if key not in facts or facts[key] in (None, "", [])]
    if missing:
        raise ValueError(f"{category} requires report facts: {', '.join(missing)}")
    if len([item for item in evidence_refs if str(item).strip()]) < policy["required_report_evidence_refs"]:
        raise ValueError(f"{category} requires at least one evidence reference")


def validate_transition(policy: dict[str, Any], action: str, evidence_refs: list[str], remediation: dict | None = None) -> None:
    if action == "confirm" and policy.get("confirmation_requires_reclassification"):
        raise ValueError("Category 'other' must be reclassified before confirmation")
    requirements = policy["transition_requirements"].get(action, {})
    if len([item for item in evidence_refs if str(item).strip()]) < requirements.get("evidence_refs", 0):
        raise ValueError(f"{action.replace('_', ' ')} requires evidence references")
    missing = [key for key in requirements.get("remediation_facts", []) if not (remediation or {}).get(key)]
    if missing:
        raise ValueError(f"remediation requires facts: {', '.join(missing)}")


def match_dependency(
    policy: dict,
    anchor_id: str,
    dependency: dict,
    facts: dict | None = None,
) -> dict[str, Any] | None:
    """Resolve exact, drawing, revision, or explicit unknown fallback matching."""

    strategy = policy["matching"]
    status = str(dependency.get("manifest_status") or "historical_unknown")
    dependency_revision = str(dependency.get("verified_source_revision") or "")
    identifiers = {str(item) for item in dependency.get("exact_anchor_ids") or []}
    if strategy == "drawing":
        return {"match_scope": "drawing", "resolution": "category_drawing_scope", "dependency_status": status}
    if strategy == "source_revision":
        known_revision = dependency_revision
        observed_revision = str((facts or {}).get("observed_revision") or "")
        expected_revision = str((facts or {}).get("expected_revision") or "")
        if known_revision and expected_revision and known_revision == expected_revision:
            return None
        if known_revision and observed_revision and known_revision != observed_revision:
            return None
        return {
            "match_scope": "source_revision" if known_revision else "drawing_fallback",
            "resolution": "source_revision" if known_revision else "historical_revision_unknown",
            "dependency_status": status,
        }
    if anchor_id in identifiers:
        return {"match_scope": "exact", "resolution": "exact_anchor", "dependency_status": status}
    if status in {"historical_unknown", "incomplete"}:
        return {"match_scope": "drawing_fallback", "resolution": "dependency_unknown_fail_closed", "dependency_status": status}
    return None


def effective_severity(policy: dict, state: str) -> str:
    severity = str(policy.get("severity") or "warning")
    if state in TERMINAL_STATES:
        return "none"
    if state == "reported" and severity == "blocking":
        return "warning"
    return severity


def governance_status(defects: list[dict[str, Any]]) -> str:
    severities = {
        str(
            item.get("effective_severity")
            or item.get("severity")
            or (item.get("policy_snapshot") or {}).get("severity")
            or ""
        )
        for item in defects
        if item.get("state") in OPEN_STATES
    }
    if "blocking" in severities:
        return "blocked"
    if "warning" in severities:
        return "warning"
    if "advisory" in severities:
        return "advisory"
    return "ready"
