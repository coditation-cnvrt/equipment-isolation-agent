from domain.enums import ObligationStatus, SourceType
from domain.hilt_geometry import valid_bbox as _valid_bbox
from domain.topology import CONTEXT_LINE_CLASSES as HILT_CONTEXT_LINE_CLASSES
from domain.topology import PROCESS_LINE_CLASSES as HILT_PROCESS_LINE_CLASSES
from domain.topology import normalize_tag


RELIEF_DEVICE_CLASS_TOKENS = ("pressure_or_vacuum_relief", "pressure_relief", "vacuum_relief", "safety_relief")
OFF_PAGE_CONNECTOR_CLASS = "off_or_on_page_connector"


def analyze_isolation_obligations(candidate_data, config):
    """Build deterministic isolation obligations for each process boundary source.

    The selected isolation candidates remain the only devices counted as barriers.
    This layer makes the boundary accounting explicit and surfaces additional
    same-source valve candidates as manual bypass/parallel-route checks.
    """
    debug = candidate_data.get("debug") or {}
    candidates = candidate_data.get("candidates") or []
    candidate_pool = candidate_data.get("_candidate_pool") or candidates
    selected_ids = {
        _norm(value)
        for candidate in candidates
        for value in (candidate.get("candidate_id"), candidate.get("visual_id"))
        if value
    }
    pool_by_source = _pool_by_source(candidate_pool)
    items = []
    seen_sources = set()
    hilt_branch_obligations = candidate_data.get("hilt_branch_obligations") or []
    relief_context_branches = _relief_context_branch_keys(hilt_branch_obligations)

    for source in hilt_branch_obligations:
        source_key = _source_key_from_item(
            {
                "equipment_tag": source.get("equipment_tag"),
                "source_component": source.get("source_component"),
                "source_component_tag": source.get("source_component_tag"),
            }
        )
        if not source_key:
            continue
        seen_sources.add(source_key)
        for branch_index, branch in enumerate(source.get("branches") or []):
            valve = branch.get("valve") or {}
            selected_for_branch = [str(valve.get("valve_id"))] if branch.get("status") == ObligationStatus.ISOLATED.value and valve.get("valve_id") else []
            manual_candidates = []
            relief_context = _branch_key(source, branch, branch_index) in relief_context_branches
            source_type = SourceType.RELIEF_CONTEXT if relief_context else SourceType.PROCESS
            status = ObligationStatus.CONTEXT.value if relief_context else (branch.get("status") or ObligationStatus.UNRESOLVED.value)
            path_ids = branch.get("path_node_ids") or []
            path_classes = branch.get("path_node_classes") or []
            items.append(
                {
                    "equipment_tag": source_key[0],
                    "source_component": source_key[1],
                    "source_component_tag": source.get("source_component_tag") or source_key[1],
                    "source_visual_id": source.get("source_visual_id"),
                    "source_type": source_type.value,
                    "status": status,
                    "selected_candidate_ids": selected_for_branch,
                    "manual_candidates": manual_candidates,
                    "manual_candidate_count": len(manual_candidates),
                    "branch_id": branch.get("branch_id"),
                    "branch_index": branch.get("branch_index"),
                    "branch_path_node_ids": path_ids,
                    "branch_path_node_classes": path_classes,
                    "branch_context_devices": branch.get("context_devices") or [],
                    **({"terminal_node": branch["terminal_node"]} if branch.get("terminal_node") else {}),
                    **(
                        {
                            "relief_role": "protective_relief_or_discharge_context",
                            "relief_device_ids": _relief_device_ids(path_ids, path_classes),
                            "requires_relief_verification": True,
                        }
                        if relief_context
                        else {}
                    ),
                    "basis": (
                        "connected HILT branch network contains an explicit pressure/vacuum relief device and no off-page process connector; treat as relief context pending safe-discharge and zero-energy verification"
                        if relief_context
                        else branch.get("basis") or "HILT branch-level process isolation obligation"
                    ),
                }
            )

    for sample in debug.get("bbox_source_visual_selection_samples") or []:
        source_key = _source_key_from_item(sample)
        if not source_key or source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        selected_for_source = [str(value) for value in sample.get("selected_candidate_ids") or [] if value]
        manual_candidates = _manual_candidates_for_source(pool_by_source.get(source_key) or [], selected_ids)
        items.append(
            {
                "equipment_tag": source_key[0],
                "source_component": source_key[1],
                "source_component_tag": _source_label(sample, pool_by_source.get(source_key) or []),
                "source_type": SourceType.PROCESS.value,
                "status": ObligationStatus.ISOLATED.value,
                "selected_candidate_ids": selected_for_source,
                "manual_candidates": manual_candidates,
                "manual_candidate_count": len(manual_candidates),
                "basis": "selected drawable isolation candidate for boundary source",
            }
        )

    for source in debug.get("bbox_unselected_source_components") or []:
        source_key = _source_key_from_item(source)
        if not source_key or source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        line_kind = "context" if source.get("source_context_type") else _line_kind(source.get("source_hilt_lines") or [])
        source_pool = pool_by_source.get(source_key) or []
        shared_selected_ids = _selected_candidate_ids_for_source(source_pool, selected_ids)
        manual_candidates = _manual_candidates_for_source(source_pool, selected_ids)
        source_type = SourceType.PROCESS if line_kind != "context" else SourceType.INSTRUMENT_CONTEXT
        if source_type == SourceType.PROCESS and shared_selected_ids:
            status = ObligationStatus.ISOLATED
        else:
            status = ObligationStatus.UNRESOLVED if source_type == SourceType.PROCESS else ObligationStatus.CONTEXT
        items.append(
            {
                "equipment_tag": source_key[0],
                "source_component": source_key[1],
                "source_component_tag": source.get("source_component_tag") or source.get("source_component_tag_raw"),
                "source_type": source_type.value,
                "status": status.value,
                "selected_candidate_ids": shared_selected_ids,
                "manual_candidates": manual_candidates,
                "manual_candidate_count": len(manual_candidates),
                "source_hilt_line_kind": line_kind,
                "source_hilt_lines": source.get("source_hilt_lines") or [],
                "min_candidate_depth": source.get("min_candidate_depth"),
                "candidate_count": source.get("candidate_count"),
                "basis": _unselected_basis(status, line_kind),
            }
        )

    for context in candidate_data.get("boundary_context_sources") or []:
        source_key = _source_key_from_item(context)
        if not source_key or source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        items.append(
            {
                "equipment_tag": source_key[0],
                "source_component": source_key[1],
                "source_component_tag": context.get("source_component_tag"),
                "source_type": SourceType.INSTRUMENT_CONTEXT.value,
                "status": ObligationStatus.CONTEXT.value,
                "selected_candidate_ids": [],
                "manual_candidates": [],
                "manual_candidate_count": 0,
                "basis": context.get("reason") or "non-process boundary context",
            }
        )

    process_items = [item for item in items if item.get("source_type") == SourceType.PROCESS.value]
    relief_items = [item for item in items if item.get("source_type") == SourceType.RELIEF_CONTEXT.value]
    unresolved_items = [item for item in process_items if item.get("status") == ObligationStatus.UNRESOLVED.value]
    manual_candidate_count = sum(len(item.get("manual_candidates") or []) for item in items)
    result = {
        "status": "completed",
        "items": items,
        "summary": {
            "obligation_count": len(items),
            "process_obligation_count": len(process_items),
            "isolated_count": sum(1 for item in process_items if item.get("status") == ObligationStatus.ISOLATED.value),
            "unresolved_count": len(unresolved_items),
            "context_count": sum(1 for item in items if item.get("status") == ObligationStatus.CONTEXT.value),
            "relief_context_count": len(relief_items),
            "relief_source_count": len({item.get("source_component") for item in relief_items if item.get("source_component")}),
            "manual_candidate_count": manual_candidate_count,
        },
        "debug": {
            "source_count": len(items),
            "manual_candidate_count": manual_candidate_count,
            "unresolved_source_ids": [item.get("source_component") for item in unresolved_items],
        },
    }
    return {**candidate_data, "isolation_obligations": result}


def _relief_context_branch_keys(sources):
    """Return unresolved branch keys belonging to a connected relief-only network.

    Connectivity is established only from exact HILT node IDs. A component must
    contain an explicitly classified relief device and must not reach an off-page
    connector. Visual labels such as "vent to atmosphere" are not used as proof.
    """
    rows = []
    for source in sources or []:
        for branch_index, branch in enumerate(source.get("branches") or []):
            if branch.get("status") != ObligationStatus.UNRESOLVED.value:
                continue
            ids = {str(value) for value in branch.get("path_node_ids") or [] if value}
            classes = {_norm(value) for value in branch.get("path_node_classes") or [] if value}
            if ids:
                rows.append({"key": _branch_key(source, branch, branch_index), "ids": ids, "classes": classes})

    components = []
    remaining = list(rows)
    while remaining:
        component = [remaining.pop(0)]
        node_ids = set(component[0]["ids"])
        changed = True
        while changed:
            changed = False
            for row in list(remaining):
                if node_ids & row["ids"]:
                    remaining.remove(row)
                    component.append(row)
                    node_ids.update(row["ids"])
                    changed = True
        components.append(component)

    result = set()
    for component in components:
        classes = set().union(*(row["classes"] for row in component))
        has_relief = any(_is_relief_device_class(value) for value in classes)
        reaches_off_page = OFF_PAGE_CONNECTOR_CLASS in classes
        if has_relief and not reaches_off_page:
            result.update(row["key"] for row in component)
    return result


def _branch_key(source, branch, branch_index):
    return (
        str(source.get("equipment_tag") or ""),
        str(source.get("source_component") or source.get("source_component_tag") or ""),
        str(branch.get("branch_id") or branch_index),
    )


def _is_relief_device_class(value):
    normalized = _norm(value)
    return any(token in normalized for token in RELIEF_DEVICE_CLASS_TOKENS)


def _relief_device_ids(path_ids, path_classes):
    return [
        str(node_id)
        for node_id, entity_class in zip(path_ids or [], path_classes or [])
        if node_id and _is_relief_device_class(entity_class)
    ]


def _pool_by_source(candidate_pool):
    grouped = {}
    for candidate in candidate_pool or []:
        if candidate.get("source_context_type"):
            continue
        source_key = _source_key_from_item(candidate)
        if source_key:
            grouped.setdefault(source_key, []).append(candidate)
    return grouped


def _manual_candidates_for_source(items, selected_ids, include_selected=False, limit=6):
    rows = []
    seen = set()
    for candidate in sorted(items or [], key=_candidate_sort_key):
        candidate_id = _norm(candidate.get("candidate_id") or candidate.get("visual_id"))
        candidate_keys = {_norm(value) for value in (candidate.get("candidate_id"), candidate.get("visual_id")) if value}
        if not candidate_id or candidate_id in seen:
            continue
        if not include_selected and candidate_keys & selected_ids:
            continue
        bbox = _valid_bbox(candidate.get("bbox"))
        if not bbox:
            continue
        seen.add(candidate_id)
        properties = candidate.get("properties") or {}
        rows.append(
            {
                "uuid": str(candidate.get("candidate_id") or candidate.get("visual_id") or ""),
                "bbox": bbox,
                "tag_number": candidate.get("tag_number"),
                "entity_class": properties.get("entity_class") or candidate.get("candidate_label"),
                "traversal_depth": candidate.get("traversal_depth"),
                "source_visual_distance": candidate.get("source_visual_distance"),
                "reason": "Additional same-source candidate; field-confirm whether this is a bypass or parallel isolation requirement.",
            }
        )
        if len(rows) >= limit:
            break
    return rows


def _selected_candidate_ids_for_source(items, selected_ids):
    result = []
    seen = set()
    for candidate in sorted(items or [], key=_candidate_sort_key):
        candidate_id = _norm(candidate.get("candidate_id") or candidate.get("visual_id"))
        candidate_keys = {_norm(value) for value in (candidate.get("candidate_id"), candidate.get("visual_id")) if value}
        if not candidate_id or not (candidate_keys & selected_ids) or candidate_id in seen:
            continue
        seen.add(candidate_id)
        result.append(str(candidate.get("candidate_id") or candidate.get("visual_id") or ""))
    return result


def _line_kind(lines):
    if not lines:
        return "unknown"
    classes = {_norm(line.get("entity_class")) for line in lines}
    types = {_norm(line.get("entity_type")) for line in lines}
    if classes & HILT_PROCESS_LINE_CLASSES or types & HILT_PROCESS_LINE_CLASSES or "process_line" in types:
        return "process"
    if classes and classes <= HILT_CONTEXT_LINE_CLASSES:
        return "context"
    return "unknown"


def _unselected_basis(status, line_kind):
    if status == ObligationStatus.CONTEXT:
        return "source lines are non-process instrument/context lines"
    if status == ObligationStatus.ISOLATED:
        return "source is covered by an isolation candidate selected for another boundary source"
    if line_kind == "unknown":
        return "source has no selected drawable isolation candidate; HILT line class is unknown"
    return "process boundary source has no selected drawable isolation candidate"


def _source_key_from_item(item):
    equipment = str(item.get("equipment_tag") or "").strip()
    source = str(
        item.get("source_component")
        or item.get("source_component_id")
        or item.get("source_component_tag")
        or ""
    ).strip()
    if not equipment or not source:
        return None
    return (equipment, source)


def _source_label(sample, pool):
    for key in ("source_component_tag", "source_component_tag_raw"):
        value = str(sample.get(key) or "").strip()
        if value:
            return value
    for candidate in pool:
        for key in ("source_display_label", "source_component_tag"):
            value = str(candidate.get(key) or "").strip()
            if value:
                return value
    return ""


def _candidate_sort_key(candidate):
    return (
        0 if _valid_bbox(candidate.get("bbox")) else 1,
        float(candidate.get("source_visual_distance") or 999999.0),
        int(candidate.get("traversal_depth") or 99),
        str(candidate.get("tag_number") or ""),
        str(candidate.get("candidate_id") or ""),
    )




# Alias, not a wrapper: normalize_tag is the single implementation.
_norm = normalize_tag
