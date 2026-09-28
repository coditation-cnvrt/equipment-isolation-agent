"""Approved UniGraph planning documents adapted for deterministic isolation runs."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from typing import Any

import httpx

from equipment_isolation.domain.plant_state import PlantStateDeclaration, ROW_FIELDS, SECTIONS
from equipment_isolation.domain.process_safety import ProcessSafetyInputs
from equipment_isolation.domain.safety_inputs import SIC_FIELDS, SicProfile


DOCUMENT_TYPES = ("fhr", "sic", "psd")
ADAPTER_VERSION = "unigraph-planning-inputs-v1"


class PlanningDocumentError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 409, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.details = details or {}


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class UniGraphPlanningDocumentClient:
    def __init__(self, auth_token: str, *, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = (base_url or os.environ.get("UNIGRAPH_API_BASE_URL") or "").rstrip("/")
        self.auth_token = str(auth_token or "").strip()
        self.timeout = timeout
        if not self.base_url:
            raise PlanningDocumentError("planning_document_service_unconfigured", "UniGraph API is not configured", 503)
        if not self.auth_token:
            raise PlanningDocumentError("planning_document_auth_required", "A user bearer token is required", 401)

    def _get(self, path: str) -> dict:
        try:
            response = httpx.get(
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self.auth_token}"},
                timeout=self.timeout,
            )
        except httpx.RequestError as exc:
            raise PlanningDocumentError(
                "planning_document_service_unavailable",
                "Unable to verify planning documents with UniGraph",
                503,
            ) from exc
        if response.status_code != 200:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            code = str(payload.get("error") or "planning_document_read_failed")
            message = str(payload.get("message") or "Unable to read planning documents")
            status = response.status_code if response.status_code in {401, 403, 404, 409, 422, 503} else 502
            raise PlanningDocumentError(code, message, status, payload)
        try:
            payload = response.json()
        except ValueError as exc:
            raise PlanningDocumentError("planning_document_response_invalid", "UniGraph returned malformed JSON", 502) from exc
        if not isinstance(payload, dict):
            raise PlanningDocumentError("planning_document_response_invalid", "UniGraph returned an invalid document response", 502)
        return payload

    def approved_bundle(self, *, unigraph_project_id: str, cnvrt_project_id: str) -> dict:
        last_error: PlanningDocumentError | None = None
        for _attempt in range(2):
            try:
                return self._approved_bundle_once(
                    unigraph_project_id=unigraph_project_id,
                    cnvrt_project_id=cnvrt_project_id,
                )
            except PlanningDocumentError as error:
                if error.code != "planning_document_read_race":
                    raise
                last_error = error
        assert last_error is not None
        raise last_error

    def _approved_bundle_once(self, *, unigraph_project_id: str, cnvrt_project_id: str) -> dict:
        project_id = str(unigraph_project_id).strip()
        bundle = self._get(f"/api/projects/{project_id}/planning-documents")
        if str(bundle.get("entry_project_id")) != project_id or str(bundle.get("cnvrt_project_id")) != str(cnvrt_project_id):
            raise PlanningDocumentError(
                "planning_document_scope_mismatch",
                "UniGraph planning documents belong to a different plant or project",
                409,
            )
        registers = {str(row.get("document_type")): row for row in bundle.get("registers") or [] if isinstance(row, dict)}
        missing = [kind for kind in DOCUMENT_TYPES if not (registers.get(kind) or {}).get("current_revision")]
        if missing:
            raise PlanningDocumentError(
                "planning_documents_missing",
                "Approved FHR, SIC and PSD documents are required",
                409,
                {"missing_document_types": missing},
            )
        manifests = {}
        for kind in DOCUMENT_TYPES:
            register = registers[kind]
            revision = register["current_revision"]
            if str(register.get("document_type") or "") != kind:
                raise PlanningDocumentError("planning_document_response_invalid", "UniGraph returned a mismatched document register", 502)
            if (
                int(register.get("id") or -1) != int(revision.get("register_id") or -2)
                or int(register.get("current_revision_id") or -1) != int(revision.get("id") or -2)
            ):
                raise PlanningDocumentError("planning_document_response_invalid", "UniGraph returned inconsistent document identifiers", 502)
            if revision.get("status") != "valid" or not isinstance(revision.get("normalized_content"), dict):
                raise PlanningDocumentError("planning_document_invalid", f"Current {kind.upper()} revision is not valid", 409)
            if revision.get("schema_version") != "planning-documents-v1":
                raise PlanningDocumentError("planning_document_schema_incompatible", f"Current {kind.upper()} schema is not supported", 409)
            if canonical_hash(revision["normalized_content"]) != revision.get("content_hash"):
                raise PlanningDocumentError("planning_document_hash_mismatch", f"Current {kind.upper()} content hash does not match", 502)
            detail = self._get(f"/api/projects/{project_id}/planning-documents/revisions/{revision['id']}")
            if (
                int(detail.get("id") or -1) != int(revision["id"])
                or int(detail.get("register_id") or -1) != int(register["id"])
                or str(detail.get("content_hash") or "") != str(revision["content_hash"])
            ):
                raise PlanningDocumentError(
                    "planning_document_read_race",
                    "Planning documents changed while their approval evidence was being read",
                    409,
                )
            approved = [
                item for item in detail.get("decisions") or []
                if item.get("decision_type") == "approved" and int(item.get("revision_id") or -1) == int(revision["id"])
            ]
            if not approved:
                raise PlanningDocumentError("planning_document_approval_missing", f"Current {kind.upper()} approval evidence is missing", 409)
            decision = max(approved, key=lambda item: int(item.get("id") or 0))
            if (
                int(decision.get("resulting_generation") or -1) != int(register["generation"])
                or not str(decision.get("actor_name") or "").strip()
                or not str(decision.get("created_at") or "").strip()
            ):
                raise PlanningDocumentError("planning_document_approval_missing", f"Current {kind.upper()} approval evidence is incomplete", 409)
            manifests[kind] = {
                "source_id": self.base_url,
                "cnvrt_project_id": str(cnvrt_project_id),
                "entry_unigraph_project_id": project_id,
                "document_type": kind,
                "register_id": int(register["id"]),
                "revision_id": int(revision["id"]),
                "revision_number": int(revision["revision_number"]),
                "generation": int(register["generation"]),
                "schema_version": str(revision["schema_version"]),
                "source_content_hash": str(revision["source_content_hash"]),
                "content_hash": str(revision["content_hash"]),
                "original_filename": str(revision["original_filename"]),
                "approval": deepcopy(decision),
                "normalized_content": deepcopy(revision["normalized_content"]),
            }
        confirmation = self._get(f"/api/projects/{project_id}/planning-documents")
        confirmed = {
            str(row.get("document_type")): (
                int(row.get("generation") or 0),
                int(row.get("current_revision_id") or 0),
            )
            for row in confirmation.get("registers") or []
            if isinstance(row, dict)
        }
        expected = {
            kind: (int(document["generation"]), int(document["revision_id"]))
            for kind, document in manifests.items()
        }
        if confirmed != expected:
            raise PlanningDocumentError(
                "planning_document_read_race",
                "Planning documents changed while their approval evidence was being read",
                409,
            )
        return {
            "schema_version": "planning-document-set-v1",
            "adapter_version": ADAPTER_VERSION,
            "source_id": self.base_url,
            "cnvrt_project_id": str(cnvrt_project_id),
            "entry_unigraph_project_id": project_id,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "documents": manifests,
            "document_set_token": canonical_hash({kind: _reference(manifests[kind]) for kind in DOCUMENT_TYPES}),
        }


def _reference(document: dict) -> dict:
    return {
        key: document[key]
        for key in (
            "source_id", "cnvrt_project_id", "document_type", "register_id", "revision_id",
            "revision_number", "generation", "schema_version", "content_hash",
        )
    }


def planning_document_summary(manifest: dict) -> dict:
    return {
        "schema_version": manifest["schema_version"],
        "adapter_version": manifest["adapter_version"],
        "source_id": manifest["source_id"],
        "cnvrt_project_id": manifest["cnvrt_project_id"],
        "entry_unigraph_project_id": manifest["entry_unigraph_project_id"],
        "captured_at": manifest["captured_at"],
        "document_set_token": manifest["document_set_token"],
        "documents": {
            kind: {**_reference(document), "original_filename": document["original_filename"], "approval": deepcopy(document["approval"])}
            for kind, document in manifest["documents"].items()
        },
    }


def planning_input_diff(captured: list[dict], current_manifest: dict, *, limit_per_document: int = 1000) -> list[dict]:
    """Compare immutable captured source snapshots with a verified current bundle."""

    current_documents = current_manifest["documents"]
    results = []
    for captured_document in sorted(captured, key=lambda item: item["document_type"]):
        kind = captured_document["document_type"]
        current = current_documents[kind]
        changes: list[dict] = []
        _json_value_changes(
            captured_document["source_snapshot"],
            current["normalized_content"],
            path="",
            result=changes,
            limit=limit_per_document + 1,
        )
        truncated = len(changes) > limit_per_document
        changes = changes[:limit_per_document]
        reference_changed = any(
            captured_document.get(key) != current.get(key)
            for key in ("register_id", "revision_id", "generation", "content_hash")
        )
        results.append({
            "document_type": kind,
            "status": "changed" if reference_changed or changes else "current",
            "captured_reference": {
                key: captured_document[key]
                for key in (
                    "source_id", "cnvrt_project_id", "document_type", "register_id",
                    "revision_id", "revision_number", "generation", "schema_version", "content_hash",
                )
            },
            "current_reference": _reference(current),
            "changes": changes,
            "truncated": truncated,
        })
    return results


def _json_value_changes(before: Any, after: Any, *, path: str, result: list[dict], limit: int) -> None:
    if len(result) >= limit or before == after:
        return
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            if len(result) >= limit:
                return
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            _json_value_changes(
                before.get(key), after.get(key), path=f"{path}/{escaped}", result=result, limit=limit
            )
        return
    if isinstance(before, list) and isinstance(after, list):
        before_index = _stable_list_index(before)
        after_index = _stable_list_index(after)
        if before_index is not None and after_index is not None:
            for identity in sorted(set(before_index) | set(after_index)):
                if len(result) >= limit:
                    return
                escaped = identity.replace("~", "~0").replace("/", "~1")
                _json_value_changes(
                    before_index.get(identity), after_index.get(identity),
                    path=f"{path}/{escaped}", result=result, limit=limit,
                )
            return
        for index in range(max(len(before), len(after))):
            if len(result) >= limit:
                return
            _json_value_changes(
                before[index] if index < len(before) else None,
                after[index] if index < len(after) else None,
                path=f"{path}/{index}", result=result, limit=limit,
            )
        return
    result.append({
        "path": path or "/",
        "before": deepcopy(before),
        "after": deepcopy(after),
        "significance": "potentially_safety_significant",
    })


def _stable_list_index(value: list[Any]) -> dict[str, Any] | None:
    if not value or not all(isinstance(item, dict) for item in value):
        return None
    result: dict[str, Any] = {}
    for item in value:
        identity = None
        if item.get("pid_service_code"):
            identity = f"service={item['pid_service_code']}|scope={item.get('unit_scope') or '*'}"
        else:
            for key in ("record_id", "fluid_code", "isolation_id", "sif_or_loop_tag", "permit_type", "name"):
                if item.get(key) not in (None, ""):
                    identity = f"{key}={item[key]}"
                    break
        if identity is None or identity in result:
            return None
        result[identity] = item
    return result


def adapt_process_safety_inputs(
    manifest: dict,
    *,
    context: dict,
    work_scope: dict,
    plan_time: str | None = None,
    unit_scope: str = "",
) -> dict:
    documents = manifest["documents"]
    fhr = _adapt_fhr(documents["fhr"], context)
    sic = _adapt_sic(documents["sic"], context)
    psd = _adapt_psd(
        documents["psd"],
        context,
        validity_hours=sic["parameters"]["plant_state"]["validity_hours"],
    )
    value = {
        "schema_version": "process-safety-inputs-v1",
        "fhr": fhr,
        "sic": sic,
        "psd": psd,
        "work_scope": deepcopy(work_scope),
        "plan_time": plan_time or datetime.now(timezone.utc).isoformat(),
        "unit_scope": str(unit_scope or (documents["psd"]["normalized_content"].get("header") or {}).get("unit") or ""),
        "controlled_documents": planning_document_summary(manifest),
    }
    return ProcessSafetyInputs.from_dict(value).to_dict()


def _adapt_fhr(document: dict, context: dict) -> dict:
    content = deepcopy(document["normalized_content"])
    decision = document["approval"]
    revision_label = _revision_label(content, document)
    value = {
        "document": {
            "title": document["original_filename"],
            "revision": revision_label,
            "status": "approved",
            "approved_by": str(decision["actor_name"]),
            "approved_date": str(decision["created_at"]),
            "cnvrt_project_id": str(context["cnvrt_project_id"]),
            "collection_id": str(context["collection_id"]),
            "unigraph_project_id": str(context["unigraph_project_id"]),
            "pnid_job_id": str(context["job_id"]),
        },
        "fluids": content.get("fluids") or [],
        "service_code_map": content.get("service_code_map") or [],
    }
    # Construction is the authoritative internal shape check.
    from equipment_isolation.domain.isolation_standard import FluidHazardRegister
    FluidHazardRegister.from_dict(value)
    return value


def _adapt_sic(document: dict, context: dict) -> dict:
    content = deepcopy(document["normalized_content"])
    criteria_keys = ("co2_ppm", "oxygen_percent_min", "oxygen_percent_max", "lel_percent", "h2s_ppm", "benzene_ppm")
    parameters = {}
    for group in SIC_FIELDS:
        source = deepcopy(content.get(group) or {})
        if group == "gas_testing":
            source["acceptance_criteria"] = {key: source.pop(key, None) for key in criteria_keys}
        parameters[group] = source
    overrides = []
    for row in content.get("matrix_overrides") or []:
        overrides.append({
            "hsc": row["hsc"], "ec": row["ec"],
            "configuration": {key: row[key] for key in (
                "barrier_count", "positive_barrier_count", "bleed_required",
                "physical_disconnection_required", "both_sides_blinded_required",
            )},
            "justification": row["justification"],
            "approver_reference": f"UniGraph decision {document['approval']['id']}",
        })
    value = {
        "schema_version": "sic-process-v1",
        "revision_label": _revision_label(content, document),
        "context": {"cnvrt_project_id": str(context["cnvrt_project_id"]), "collection_id": str(context["collection_id"])},
        "synthetic": False,
        "parameters": parameters,
        "matrix_overrides": overrides,
        "unresolved_decisions": [],
        "source_provenance": {"adapter_version": ADAPTER_VERSION, "document": _reference(document)},
    }
    return SicProfile.from_dict(value).to_dict()


def _adapt_psd(document: dict, context: dict, *, validity_hours: float) -> dict:
    content = deepcopy(document["normalized_content"])
    header = deepcopy(content.get("header") or {})
    if header.get("valid_until") is None and header.get("declared_at"):
        declared_at = datetime.fromisoformat(str(header["declared_at"]).replace("Z", "+00:00"))
        header["valid_until"] = (declared_at + timedelta(hours=float(validity_hours))).isoformat()
    value = {
        "schema_version": "psd-v1",
        "revision_label": _revision_label(content, document),
        "context": {key: str(context[key]) for key in ("cnvrt_project_id", "collection_id", "unigraph_project_id", "job_id")},
        "synthetic": False,
        "header": header,
        "section_coverage": deepcopy(content.get("section_coverage") or {}),
        "source_provenance": {"adapter_version": ADAPTER_VERSION, "document": _reference(document), "row_annotations": {}},
    }
    for section in SECTIONS:
        value[section] = []
        value["source_provenance"]["row_annotations"][section] = {}
        identity_key = ROW_FIELDS[section][0]
        for index, source in enumerate(content.get(section) or []):
            row = deepcopy(source)
            record_id = str(row.pop("record_id", None) or "")
            if section != "active_overrides":
                row[identity_key] = record_id or str(row.get(identity_key) or f"{section}-{index + 1}")
            if section in {"equipment_state", "system_status", "valve_position_exceptions"}:
                row.setdefault("hilt_entity_id", None)
                row.setdefault("unigraph_vertex_id", None)
            if section == "equipment_state":
                row["remarks"] = str(row.get("remarks") or "")
            if section == "system_status":
                row["remarks"] = str(row.get("remarks") or "")
            allowed = set(ROW_FIELDS[section])
            annotations = {"record_id": record_id} if record_id else {}
            annotations.update({
                key: item for key, item in row.items() if key not in allowed
            })
            value["source_provenance"]["row_annotations"][section][row[identity_key]] = annotations
            value[section].append({key: row.get(key) for key in ROW_FIELDS[section]})
    return PlantStateDeclaration.from_dict(value).to_dict()


def _revision_label(content: dict, document: dict) -> str:
    for key in ("revision", "revision_label"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    fluids = content.get("fluids") or []
    labels = {str(row.get("revision") or "").strip() for row in fluids if str(row.get("revision") or "").strip()}
    if len(labels) == 1:
        return labels.pop()
    return f"revision-{document['revision_number']}"
