"""B1 input contracts. These validate declared data, not execution authority."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re

from equipment_isolation.domain.controlled_inputs import (
    ControlledInputError, canonical_bytes, content_hash, utc_timestamp,
)


def invalid(path, message):
    raise ControlledInputError("invalid_safety_input", f"{path}: {message}")


def obj(value, keys, path, optional=()):
    if type(value) is not dict:
        invalid(path, "expected object")
    if set(value) - set(keys) - set(optional) or set(keys) - set(value):
        invalid(path, "missing or unsupported fields")
    return value


def string(value, path):
    if type(value) is not str or not value.strip():
        invalid(path, "expected non-empty string")
    return value.strip()


def number(value, path, minimum=None, maximum=None, integer=False):
    if type(value) not in ((int,) if integer else (int, float)):
        invalid(path, "expected number" if not integer else "expected integer")
    canonical_bytes(value)  # Reject non-finite values, including deeply nested input.
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        invalid(path, "outside allowed range")
    return value


def boolean(value, path):
    if type(value) is not bool:
        invalid(path, "expected boolean")
    return value


def enum(value, choices, path):
    if type(value) is not str or value not in choices:
        invalid(path, f"expected one of {', '.join(sorted(choices))}")
    return value


def strings(value, path, nonempty=False):
    if type(value) is not list or nonempty and not value:
        invalid(path, "expected string array")
    result = [string(item, path) for item in value]
    if len(set(result)) != len(result):
        invalid(path, "duplicate values")
    return sorted(result)


def timestamp(value, path):
    value = string(value, path)
    try:
        # Date-only and naive values are rejected by utc_timestamp.
        return utc_timestamp(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except (ValueError, OverflowError) as exc:
        invalid(path, f"expected timestamp with timezone ({type(exc).__name__})")


def digest(value, path):
    if type(value) is not str or not re.fullmatch("[0-9a-f]{64}", value):
        invalid(path, "expected SHA-256 hex digest")
    return value


def context(value, *, drawing=True):
    keys = ["cnvrt_project_id", "collection_id"]
    if drawing:
        keys += ["unigraph_project_id", "job_id"]
    obj(value, keys, "context")
    result = {}
    for key in keys:
        if type(value[key]) not in (int, str):
            invalid(key, "expected explicit source identity")
        result[key] = string(str(value[key]), key)
    return result


@dataclass(frozen=True)
class FrozenJSON:
    """Canonical immutable storage, including nested objects and arrays.

    Every projection is detached. Construction from bytes also validates, so the
    normal dataclass constructor cannot bypass a subclass's contract.
    """
    _canonical: bytes

    def __post_init__(self):
        if type(self._canonical) is not bytes:
            invalid("document", "use from_dict or canonical JSON bytes")
        try:
            def unique_object(pairs):
                result = {}
                for key, item in pairs:
                    if key in result:
                        invalid("document", "duplicate JSON object key")
                    result[key] = item
                return result
            value = json.loads(self._canonical, object_pairs_hook=unique_object)
        except (ValueError, UnicodeError):
            invalid("document", "invalid JSON")
        canonical_bytes(value)
        normalized = self._validate(value)
        object.__setattr__(self, "_canonical", canonical_bytes(normalized))

    @staticmethod
    def _validate(value):
        if type(value) is not dict:
            invalid("document", "expected object")
        return value

    @classmethod
    def from_dict(cls, value):
        return cls(canonical_bytes(value))

    def to_dict(self):
        return json.loads(self._canonical)

    @property
    def content_hash(self):
        return content_hash(self.to_dict())


class StructuredWorkScope(FrozenJSON):
    @staticmethod
    def _validate(value):
        flags = ("containment_break", "continuously_attended", "personnel_enter_boundary",
                 "hot_work_on_or_within_boundary", "equipment_leaves_site")
        obj(value, ["schema_version", "activity_type", "expected_duration_days", "shift_coverage", *flags], "work_scope")
        enum(value["schema_version"], {"work-scope-v1"}, "schema_version")
        value["activity_type"] = string(value["activity_type"], "activity_type")
        number(value["expected_duration_days"], "expected_duration_days", minimum=0)
        enum(value["shift_coverage"], {"single_shift", "multiple_shifts"}, "shift_coverage")
        for key in flags:
            boolean(value[key], key)
        return value


# No product defaults are inserted. Values must be supplied by a controlled source.
def _positive(value, path):
    number(value, path, minimum=0)
    if value == 0:
        invalid(path, "must be positive")
    return value


def _nullable(check):
    return lambda value, path: None if value is None else check(value, path)


def _choice(*values):
    return lambda value, path: enum(value, set(values), path)


SIC_FIELDS = {
    "barrier_policy": {
        "check_valve_role": _choice("none", "secondary_below_hsc3"),
        "actuated_valve_as_barrier": _choice("allowed", "not_allowed", "allowed_if_lockable"),
        "soft_seat_permitted_for_hot_work": boolean, "small_bore_threshold_dn": _positive,
    },
    "escalation_thresholds": {
        "duration_escalate_days": _positive, "positive_isolation_mandatory_days": _positive,
        "unattended_overnight_escalates": boolean, "shift_change_requires_reprove": boolean,
    },
    "proving": {
        "pressure_decay_hold_minutes": _nullable(_positive), "acceptance_criterion": _nullable(string),
        "re_prove_interval_hours": _nullable(_positive), "revalidation_triggers": strings,
        "test_procedure_reference": _nullable(string),
    },
    "plant_state": {
        "validity_hours": _positive, "condition_change_requires_redeclaration": boolean,
        "field_verification_required": boolean,
    },
    "gas_testing": {
        "required_analytes": strings, "retest_interval_minutes": _nullable(_positive),
        "procedure_reference": _nullable(string),
    },
    "purging": {
        "target_oxygen_percent": _nullable(lambda v, p: number(v, p, minimum=0, maximum=100)),
        "volume_changes": _nullable(_positive), "permitted_media": strings,
        "approved_procedure_reference": _nullable(string),
    },
    "tagging": {
        "lock_colour_scheme": _nullable(string), "tag_numbering_format": string,
        "hasp_box_policy": string, "personal_lock_policy": string,
    },
    "electrical": {"electrical_isolation_mode": _choice("out_of_scope", "manual_input", "sld_graph")},
    "modes": {"emergency_mode_enabled": boolean},
    "export": {"cmms_adapter": _choice("none", "maximo", "sap_pm", "canonical")},
}
GAS_FIELDS = {"co2_ppm", "oxygen_percent_min", "oxygen_percent_max", "lel_percent", "h2s_ppm", "benzene_ppm"}
CONFIG_FIELDS = {"barrier_count", "bleed_required", "positive_barrier_count", "physical_disconnection_required", "both_sides_blinded_required"}


def configuration(value):
    obj(value, CONFIG_FIELDS, "configuration")
    number(value["barrier_count"], "barrier_count", minimum=1, integer=True)
    number(value["positive_barrier_count"], "positive_barrier_count", minimum=0, maximum=value["barrier_count"], integer=True)
    for name in CONFIG_FIELDS - {"barrier_count", "positive_barrier_count"}:
        boolean(value[name], name)
    if value["both_sides_blinded_required"] and not value["physical_disconnection_required"]:
        invalid("configuration", "both-side blinding requires disconnection")
    if value["physical_disconnection_required"] and (value["barrier_count"] < 2 or value["positive_barrier_count"] < 2):
        invalid("configuration", "disconnection requires two positive barriers")
    return value


def matrix_overrides(rows):
    if type(rows) is not list:
        invalid("matrix_overrides", "expected array")
    seen = set()
    for row in rows:
        obj(row, ["hsc", "ec", "configuration", "justification", "approver_reference"], "matrix_override")
        number(row["hsc"], "hsc", minimum=1, maximum=4, integer=True)
        enum(row["ec"], set("ABCD"), "ec")
        configuration(row["configuration"])
        row["justification"] = string(row["justification"], "justification")
        row["approver_reference"] = string(row["approver_reference"], "approver_reference")
        cell = row["hsc"], row["ec"]
        if cell in seen:
            invalid("matrix_overrides", "duplicate cell")
        seen.add(cell)
    return sorted(rows, key=lambda row: (row["hsc"], row["ec"]))


class SicProfile(FrozenJSON):
    """Validated draft profile; approval references are claims, not authority."""
    @staticmethod
    def _validate(value):
        obj(value, ["schema_version", "revision_label", "context", "synthetic", "parameters",
                    "matrix_overrides", "unresolved_decisions", "source_provenance"], "sic")
        enum(value["schema_version"], {"sic-process-v1"}, "schema_version")
        value["revision_label"] = string(value["revision_label"], "revision_label")
        value["context"] = context(value["context"], drawing=False)
        boolean(value["synthetic"], "synthetic")
        params = obj(value["parameters"], SIC_FIELDS, "parameters")
        for group, validators in SIC_FIELDS.items():
            optional = ["acceptance_criteria"] if group == "gas_testing" else []
            row = obj(params[group], validators, group, optional)
            for key, check in validators.items():
                row[key] = check(row[key], f"{group}.{key}")
        criteria = obj(params["gas_testing"].get("acceptance_criteria"), GAS_FIELDS, "gas_testing.acceptance_criteria")
        for key in GAS_FIELDS:
            if criteria[key] is not None:
                number(criteria[key], key, minimum=0, maximum=100 if "percent" in key else None)
        low, high = criteria["oxygen_percent_min"], criteria["oxygen_percent_max"]
        if (low is None) != (high is None) or low is not None and low > high:
            invalid("oxygen_percent", "supply an ordered pair or two unknowns")
        value["matrix_overrides"] = matrix_overrides(value["matrix_overrides"])
        value["unresolved_decisions"] = strings(value["unresolved_decisions"], "unresolved_decisions")
        # Provenance is annotation only and cannot introduce parameter values.
        if type(value["source_provenance"]) is not dict:
            invalid("source_provenance", "expected object")
        return value

    @property
    def blockers(self):
        value = self.to_dict()
        gaps = {"sic_approval_not_integrated", "safety_policy_decisions_pending"}
        if value["synthetic"] or value["revision_label"].upper().startswith("MOCK-"):
            gaps.add("synthetic_input")
        for name in value["unresolved_decisions"]:
            gaps.add(f"sic_decision:{name}")
        for key, val in value["parameters"]["proving"].items():
            if val is None:
                gaps.add(f"sic_missing:proving.{key}")
        if value["parameters"]["electrical"]["electrical_isolation_mode"] != "out_of_scope":
            gaps.add("electrical_mode_not_implemented")
        if value["parameters"]["modes"]["emergency_mode_enabled"]:
            gaps.add("emergency_mode_not_implemented")
        return tuple(sorted(gaps))


class SicDelta(FrozenJSON):
    @staticmethod
    def _validate(value):
        obj(value, ["schema_version", "revision_label", "context", "synthetic", "base_hash",
                    "base_revision_label", "changes", "justification"], "sic_delta")
        enum(value["schema_version"], {"sic-process-delta-v1"}, "schema_version")
        value["context"] = context(value["context"], drawing=False)
        for key in ("revision_label", "base_revision_label", "justification"):
            value[key] = string(value[key], key)
        boolean(value["synthetic"], "synthetic")
        digest(value["base_hash"], "base_hash")
        if type(value["changes"]) is not dict or not value["changes"]:
            invalid("changes", "expected non-empty path-to-value object")
        allowed = {f"/parameters/{g}/{k}" for g, spec in SIC_FIELDS.items() for k in spec}
        allowed |= {"/parameters/gas_testing/acceptance_criteria", "/matrix_overrides"}
        if set(value["changes"]) - allowed:
            invalid("changes", "unsupported path; identity/approval/floors cannot be edited")
        return value


class ConfigurationFloor(FrozenJSON):
    @staticmethod
    def _validate(value):
        obj(value, ["rule_id", "source_hash", "hsc", "ec", "configuration"], "configuration_floor")
        value["rule_id"] = string(value["rule_id"], "rule_id")
        digest(value["source_hash"], "source_hash")
        number(value["hsc"], "hsc", minimum=1, maximum=4, integer=True)
        enum(value["ec"], set("ABCD"), "ec")
        configuration(value["configuration"])
        return value


def compose_sic(base: SicProfile, delta: SicDelta | None = None, *, floors: tuple[ConfigurationFloor, ...] = ()) -> tuple[SicProfile, FrozenJSON]:
    """Explicit leaf replacement followed by full validation; no recursive merge.

    Floors are intentionally outside SIC-editable content. The later RBC engine
    must apply controlled pattern floors after this profile's overrides.
    """
    if not isinstance(base, SicProfile) or delta is not None and not isinstance(delta, SicDelta):
        invalid("composition", "expected validated SIC profile and delta contracts")
    value = base.to_dict()
    origins = {f"/parameters/{group}/{key}": base.content_hash for group, row in value["parameters"].items() for key in row}
    origins["/matrix_overrides"] = base.content_hash
    if delta is not None:
        patch = delta.to_dict()
        if patch["base_hash"] != base.content_hash or patch["base_revision_label"] != value["revision_label"]:
            invalid("base_hash", "delta targets a different base revision")
        if patch["context"] != value["context"]:
            invalid("context", "delta belongs to a different collection")
        for path, replacement in patch["changes"].items():
            target = value
            parts = path[1:].split("/")
            for key in parts[:-1]:
                target = target[key]
            target[parts[-1]] = replacement
            origins[path] = delta.content_hash
        value["synthetic"] = value["synthetic"] or patch["synthetic"] or patch["revision_label"].upper().startswith("MOCK-")
    profile = SicProfile.from_dict(value)
    if type(floors) is not tuple or any(not isinstance(floor, ConfigurationFloor) for floor in floors):
        invalid("floors", "expected immutable floor tuple")
    floor_rows = sorted([floor.to_dict() for floor in floors], key=lambda row: (row["hsc"], row["ec"], row["rule_id"], row["source_hash"]))
    if len({(row["hsc"], row["ec"], row["rule_id"]) for row in floor_rows}) != len(floor_rows):
        invalid("floors", "duplicate floor rule/cell")
    for floor in floor_rows:
        for override in value["matrix_overrides"]:
            if (override["hsc"], override["ec"]) == (floor["hsc"], floor["ec"]):
                for key, requirement in floor["configuration"].items():
                    if override["configuration"][key] < requirement:
                        invalid("matrix_override", "override weakens a non-overridable floor")
    composition = FrozenJSON.from_dict({
        "schema_version": "sic-composition-v1", "base_hash": base.content_hash,
        "delta_hash": delta.content_hash if delta else None, "effective_hash": profile.content_hash,
        "parameter_origins": origins, "non_overridable_floors": floor_rows,
    })
    return profile, composition
