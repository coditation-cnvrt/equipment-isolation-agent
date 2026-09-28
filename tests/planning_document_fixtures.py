"""Sanitized UniGraph planning-document contract fixtures."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from importlib.resources import files
import json

from equipment_isolation.integrations.planning_documents import (
    ADAPTER_VERSION,
    adapt_process_safety_inputs,
    canonical_hash,
)
from equipment_isolation.integrations.safety_input_adapters import psd_from_mock, sic_from_mock


CONTEXT = {
    "cnvrt_project_id": "277",
    "collection_id": "206",
    "unigraph_project_id": "21",
    "job_id": "2151",
}
WORK_SCOPE = {
    "schema_version": "work-scope-v1",
    "activity_type": "Equipment inspection",
    "expected_duration_days": 1,
    "shift_coverage": "single_shift",
    "containment_break": True,
    "continuously_attended": True,
    "personnel_enter_boundary": False,
    "hot_work_on_or_within_boundary": False,
    "equipment_leaves_site": False,
}


def _mock(kind: str) -> dict:
    return json.loads(files("equipment_isolation.fixtures").joinpath(f"mock_{kind}_pnid_2151.json").read_text())


def _upstream_fhr() -> dict:
    source = _mock("fhr")
    return {"fluids": deepcopy(source["fluids"]), "service_code_map": deepcopy(source["service_code_map"])}


def _upstream_sic() -> dict:
    source = sic_from_mock(_mock("sic")).to_dict()
    result = deepcopy(source["parameters"])
    result["matrix_overrides"] = [
        {
            "record_id": f"matrix-{index + 1}",
            "hsc": row["hsc"],
            "ec": row["ec"],
            **row["configuration"],
            "justification": row["justification"],
        }
        for index, row in enumerate(source["matrix_overrides"])
    ]
    result["permits"] = []
    return result


def _upstream_psd() -> dict:
    source = psd_from_mock(_mock("psd")).to_dict()
    result = {
        "header": deepcopy(source["header"]),
        "section_coverage": deepcopy(source["section_coverage"]),
    }
    for section in ("equipment_state", "system_status", "valve_position_exceptions", "active_isolations", "active_overrides"):
        result[section] = []
        for index, original in enumerate(source[section]):
            row = deepcopy(original)
            identity = row.pop("row_id", None) or row.pop("isolation_id", None) or f"{section}-{index + 1}"
            row = {"record_id": identity, **row}
            if section in {"equipment_state", "system_status", "valve_position_exceptions"}:
                row["job_id"] = CONTEXT["job_id"]
            result[section].append(row)
    return result


def approved_manifest(*, generation: int = 1, fhr_revision_id: int = 101) -> dict:
    normalized = {"fhr": _upstream_fhr(), "sic": _upstream_sic(), "psd": _upstream_psd()}
    documents = {}
    for index, kind in enumerate(("fhr", "sic", "psd"), start=1):
        revision_id = fhr_revision_id if kind == "fhr" else 100 + index
        content = normalized[kind]
        documents[kind] = {
            "source_id": "http://unigraph.example/plantgraph",
            "cnvrt_project_id": CONTEXT["cnvrt_project_id"],
            "entry_unigraph_project_id": CONTEXT["unigraph_project_id"],
            "document_type": kind,
            "register_id": index,
            "revision_id": revision_id,
            "revision_number": generation,
            "generation": generation,
            "schema_version": "planning-documents-v1",
            "source_content_hash": canonical_hash({"source": kind, "generation": generation}),
            "content_hash": canonical_hash(content),
            "original_filename": f"plant-{kind}.csv",
            "approval": {
                "id": 200 + index,
                "revision_id": revision_id,
                "decision_type": "approved",
                "actor_id": "operations-reviewer",
                "actor_name": "Operations Reviewer",
                "reason": "Approved test fixture",
                "expected_generation": generation - 1,
                "resulting_generation": generation,
                "created_at": "2026-09-17T07:00:00+00:00",
            },
            "normalized_content": content,
        }
    manifest = {
        "schema_version": "planning-document-set-v1",
        "adapter_version": ADAPTER_VERSION,
        "source_id": "http://unigraph.example/plantgraph",
        "cnvrt_project_id": CONTEXT["cnvrt_project_id"],
        "entry_unigraph_project_id": CONTEXT["unigraph_project_id"],
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "documents": documents,
    }
    manifest["document_set_token"] = canonical_hash({
        kind: {
            key: document[key]
            for key in ("source_id", "cnvrt_project_id", "document_type", "register_id", "revision_id", "revision_number", "generation", "schema_version", "content_hash")
        }
        for kind, document in documents.items()
    })
    return manifest


def governed_inputs(manifest: dict | None = None) -> dict:
    return adapt_process_safety_inputs(
        manifest or approved_manifest(),
        context=CONTEXT,
        work_scope=WORK_SCOPE,
        plan_time="2026-09-17T08:00:00+00:00",
        unit_scope="",
    )
