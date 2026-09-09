"""Versioned controlled-content serialization; no persistence or approval authority."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math

from equipment_isolation.domain.isolation_standard import (
    FhrDocument, FluidHazard, FluidHazardRegister, ServiceCodeMapping,
    IsolationStandardValidationError,
)

CANONICAL_VERSION = "controlled-json-v1"
FHR_SCHEMA = "fhr-v1"


class ControlledInputError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def canonical_bytes(value) -> bytes:
    """UTF-8 JSON; finite numbers in plain decimal, -0 == 0; arrays retain order.

    Float values use Python's shortest round-trip decimal. Datetimes must be
    explicitly projected with utc_timestamp; arbitrary objects are never coerced.
    """
    def encode(item):
        if item is None:
            return "null"
        if type(item) is bool:
            return "true" if item else "false"
        if type(item) is int:
            return str(item)
        if type(item) is float:
            if not math.isfinite(item):
                raise ControlledInputError("invalid_content", "Non-finite number")
            number = format(Decimal(repr(item)), "f")
            if "." in number:
                number = number.rstrip("0").rstrip(".")
            return "0" if item == 0 else number
        if type(item) is str:
            return json.dumps(item, ensure_ascii=False)
        if type(item) is list:
            return "[" + ",".join(encode(x) for x in item) + "]"
        if type(item) is dict and all(type(k) is str for k in item):
            return "{" + ",".join(encode(k) + ":" + encode(item[k]) for k in sorted(item)) + "}"
        raise ControlledInputError("invalid_content", "Only JSON values with string object keys are supported")
    try:
        return encode(value).encode("utf-8")
    except UnicodeError as exc:
        raise ControlledInputError("invalid_content", "Invalid Unicode") from exc


def content_hash(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def utc_timestamp(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ControlledInputError("invalid_time", "An explicit timezone is required")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def scope_for(input_type: str, context: dict) -> dict:
    if input_type not in {"fhr", "sic"} or not isinstance(context, dict):
        raise ControlledInputError("invalid_scope", "Supported types are fhr and sic")
    result = {}
    for key in ("cnvrt_project_id", "collection_id", "job_id"):
        value = context.get(key)
        if input_type == "sic" and key == "job_id":
            result[key] = ""
        elif type(value) not in {str, int} or not str(value).strip():
            raise ControlledInputError("invalid_scope", f"Missing explicit {key}")
        else:
            result[key] = str(value).strip()
    return result


def prepare_content(input_type: str, schema_version: str, payload: dict) -> tuple[dict, dict]:
    canonical_bytes(payload)  # Reject non-JSON/NaN even in uninterpreted metadata.
    if not isinstance(payload, dict):
        raise ControlledInputError("invalid_content", "Content must be an object")
    if "metadata" in payload and not isinstance(payload["metadata"], dict):
        raise ControlledInputError("invalid_content", "metadata must be an object")
    result = deepcopy(payload)
    if input_type == "sic" and schema_version == "sic-process-v1":
        # B1 validates drafts without granting approval or enabling runtime use.
        from equipment_isolation.domain.safety_inputs import SicProfile
        profile = SicProfile.from_dict(result)
        return profile.to_dict(), {"status": "draft_validated", "schema_version": schema_version,
                                   "blockers": list(profile.blockers)}
    if input_type != "fhr" or schema_version != FHR_SCHEMA:
        return result, {"status": "unsupported", "schema_version": schema_version}
    try:
        register = FluidHazardRegister.from_dict(result)
    except IsolationStandardValidationError as exc:
        raise ControlledInputError("invalid_fhr", str(exc)) from exc
    # Unknown fields, including alternate unit fields, must not silently disappear.
    allowed = {"document", "fluids", "service_code_map", "metadata"}
    if set(result) - allowed:
        raise ControlledInputError("invalid_fhr", "Unsupported FHR top-level fields; use metadata for source annotations")
    for rows, model in (([result["document"]], FhrDocument), (result["fluids"], FluidHazard), (result["service_code_map"], ServiceCodeMapping)):
        for row in rows:
            if set(row) - {field.name for field in fields(model)}:
                raise ControlledInputError("invalid_fhr", "Unsupported FHR fields or units")
    result["fluids"].sort(key=lambda row: row["fluid_code"].strip().upper())
    for row in result["fluids"]:
        if isinstance(row.get("special_hazards"), list):
            row["special_hazards"] = sorted(row["special_hazards"])
    result["service_code_map"].sort(key=lambda row: (row["pid_service_code"].strip().upper(), (row.get("unit_scope") or "").strip().lower(), row["fluid_code"].strip().upper()))
    return result, {"status": "valid", "schema_version": schema_version, "fluid_count": len(register.fluids)}


def validate_approval(input_type: str, schema_version: str, payload: dict) -> None:
    _, validation = prepare_content(input_type, schema_version, payload)
    if validation["status"] != "valid":
        raise ControlledInputError("unsupported_schema", "No approval validator exists for this input schema")
    if "mock" in payload["document"]["status"].lower() or payload["document"]["revision"].upper().startswith("MOCK-") or payload.get("metadata", {}).get("synthetic"):
        raise ControlledInputError("mock_unapprovable", "Synthetic development FHR cannot be approved")


def approved_fhr(revision: dict) -> FluidHazardRegister:
    """Adapt a trusted repository projection, never an HTTP request.

    The terminal decision approves the whole submitted document and every row.
    Imported document/row approval claims remain in the stored payload/hash; the
    runtime value receives server decision metadata without altering that payload.
    """
    if revision.get("decision") != "approved" or not revision.get("decided_by") or not revision.get("decided_at"):
        raise ControlledInputError("input_unapproved", "Repository approval decision required")
    validate_approval(revision["input_type"], revision["schema_version"], revision["payload"])
    if content_hash(revision["payload"]) != revision["content_hash"]:
        raise ControlledInputError("hash_mismatch", "Controlled content hash mismatch")
    register = FluidHazardRegister.from_dict(revision["payload"])
    actor, timestamp = revision["decided_by"], revision["decided_at"]
    register = replace(register, document=replace(register.document, status="approved", approved_by=actor, approved_date=timestamp), fluids=tuple(replace(row, approved_by=actor, approved_date=timestamp) for row in register.fluids))
    register.assert_approved()
    return register
