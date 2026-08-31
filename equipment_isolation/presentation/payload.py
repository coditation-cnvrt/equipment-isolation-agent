"""Final UI payload assembly (pipeline stage 13).

Pure dict construction -- no filesystem, no HTML. Split out of output.py so the
agent tool layer can build payloads without importing the HTML renderer.
Covered by tests/test_payload.py.
"""
from equipment_isolation.domain.identity import RESULT_SCHEMA_VERSION
from equipment_isolation.domain.isolation_actions import operation_kind, requires_positive_field_confirmation
from equipment_isolation.domain.serialization import to_jsonable  # noqa: F401  (re-exported for callers)
from equipment_isolation.core.secondary_context import build_secondary_energy_context


def build_final_payload(validation_data, config, downstream_impact=None):
    candidates = validation_data.get("candidates", []) or []
    context = validation_data.get("context") or config.context
    manual_visual_checks = validation_data.get("manual_visual_isolation_checks") or []
    context_instruments = (validation_data.get("isolation_validation") or {}).get("context_instruments") or validation_data.get("context_instruments") or []
    boundary_context_sources = (validation_data.get("isolation_validation") or {}).get("boundary_context_sources") or validation_data.get("boundary_context_sources") or context_instruments
    selected_equipment_overlays = validation_data.get("selected_equipment_overlays") or []
    isolation_obligations = validation_data.get("isolation_obligations") or (validation_data.get("isolation_validation") or {}).get("isolation_obligations") or {}
    instrument_context = validation_data.get("instrument_context") or {}
    isolated_envelope = validation_data.get("isolated_envelope") or {}
    detected_isolation_schemes = validation_data.get("detected_isolation_schemes") or {}
    relief_candidates = validation_data.get("relief_candidates") or {}
    target_identity = validation_data.get("target_identity") or {
        "status": "legacy_tag_only",
        "identity_quality": "legacy_tag_only",
        "tag": config.equipment_tag,
    }
    secondary_energy_context = validation_data.get("secondary_energy_context") or build_secondary_energy_context(validation_data)
    isolation_points = []
    for candidate in candidates:
        properties = candidate.get("properties", {}) or {}
        entity_class = properties.get("entity_class") or candidate.get("candidate_label")
        drawing_entity_id = candidate.get("visual_node_id") or candidate.get("visual_id")
        isolation_points.append(
            {
                "equipment_id": candidate.get("equipment_tag"),
                "uuid": str(candidate.get("plan_point_id") or candidate.get("candidate_id")),
                # The isolation device's exact HILT drawing identity. Keep this
                # separate from source_visual_id, which identifies the source
                # nozzle and must never be highlighted as the barrier device.
                "drawing_entity_id": str(drawing_entity_id) if drawing_entity_id not in (None, "") else None,
                "bbox": candidate.get("bbox") or [],
                "bbox_source": candidate.get("visual_source"),
                "bbox_match_method": candidate.get("bbox_match_method"),
                "entity_class": entity_class,
                "tag_number": candidate.get("tag_number"),
                "energy_type": (candidate.get("energy_type") or ["process"])[0],
                "isolation_method": candidate.get("isolation_method"),
                "operation_kind": operation_kind(entity_class),
                "positive_isolation_requires_field_confirmation": requires_positive_field_confirmation(entity_class),
                "policy_decision": candidate.get("policy_decision") or (candidate.get("classification") or {}).get("decision"),
                "requires_manual_review": bool(candidate.get("requires_manual_review")),
                "availability_status": candidate.get("availability_status") or "available",
                "available_for_isolation": candidate.get("available_for_isolation") is not False,
                "unavailable_reason": candidate.get("unavailable_reason"),
                "source_component": candidate.get("source_component_id") or candidate.get("source_component_tag"),
                "source_component_tag": candidate.get("source_component_tag"),
                "source_visual_id": candidate.get("source_visual_id"),
                "required_branch_isolation": bool(candidate.get("required_branch_isolation")),
                "branch_id": candidate.get("branch_id"),
                "branch_status": candidate.get("branch_status"),
                "branch_basis": candidate.get("branch_basis"),
                "branch_path_node_ids": candidate.get("branch_path_node_ids") or [],
                "branch_path_node_classes": candidate.get("branch_path_node_classes") or [],
                "branch_context_devices": candidate.get("branch_context_devices") or [],
                "source_paths": candidate.get("source_paths") or [],
                "reason": f"{candidate.get('reason')}. Candidate vertex id: {candidate.get('candidate_id')}. Source component: {candidate.get('source_component_tag')}.",
                "provenance": candidate.get("provenance") or "derived",
                "correction_provenance": candidate.get("correction_provenance"),
            }
        )
    return {
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "error": False,
        "message": "Completed",
        "debug": validation_data.get("debug", {}),
        "data": [
            {
                "job_id": _int_or_text(context.get("job_id")),
                "job_name": context.get("job_name"),
                "project_id": _int_or_text(context.get("project_id")),
                "project_name": f"Project {context.get('project_id')}",
                "collection_id": _int_or_text(context.get("collection_id")),
                "collection_name": context.get("collection_name"),
                "selected_equipment": [config.equipment_tag],
                "target_identity": target_identity,
                "input_details": {**context, "selected_equipment": [config.equipment_tag], "target_mode": "selected_equipment"},
                "assurance_status": validation_data.get("assurance_status"),
                "plan_readiness": validation_data.get("plan_readiness") or (validation_data.get("isolation_validation") or {}).get("plan_readiness"),
                "isolation_validation": validation_data.get("isolation_validation"),
                "unselected_boundary_sources": (validation_data.get("isolation_validation") or {}).get("unselected_boundary_sources") or [],
                "boundary_context_sources": boundary_context_sources,
                "context_instruments": context_instruments,
                "manual_visual_isolation_checks": manual_visual_checks,
                "selected_equipment_overlays": selected_equipment_overlays,
                "isolation_points": isolation_points,
                "isolation_obligations": isolation_obligations,
                "downstream_impact": downstream_impact or validation_data.get("downstream_impact"),
                "instrument_context": instrument_context,
                "secondary_energy_context": secondary_energy_context,
                "isolated_envelope": isolated_envelope,
                "detected_isolation_schemes": detected_isolation_schemes,
                "relief_candidates": relief_candidates,
                "correction_coverage": validation_data.get("correction_coverage") or [],
            }
        ],
    }


def _int_or_text(value):
    try:
        return int(value)
    except Exception:
        return value
