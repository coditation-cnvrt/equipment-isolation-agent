SAFETY_CRITICAL_CHECKS = {
    "find_bypass_paths",
    "find_blinds_spades_flanges",
    "find_bleeds_vents_drains",
    "find_pressure_indicators",
}


def plan_requests(evidence_data, config):
    evidence = evidence_data.get("evidence_state") or {}
    context = evidence_data.get("context") or config.context
    checks = []
    args = {
        "job_id": context.get("job_id"),
        "job_name": context.get("job_name"),
        "project_id": context.get("project_id"),
        "collection_id": context.get("collection_id"),
    }
    if not evidence.get("verification_candidate_ids"):
        checks.append(_check("find_bleeds_vents_drains", "Find stored-energy release points for proving zero or safe energy.", args, "high", _relief_targets(evidence_data)))
        checks.append(_check("find_pressure_indicators", "Find pressure gauges, pressure indicators, or approved test points near isolated sections.", args, "high", _pressure_targets(evidence_data)))
    if config.work_scope.requires_positive_isolation and not evidence.get("positive_candidate_ids"):
        checks.append(_check("find_blinds_spades_flanges", "Work scope requires positive isolation evidence.", args, "high"))
    checks.append(_check("find_bypass_paths", "Check for bypasses or alternate routes around selected barriers.", args, "medium", _topology_review_targets(evidence_data)))
    if not evidence.get("positive_candidate_ids") or not evidence.get("verification_candidate_ids"):
        checks.append(_check("fetch_pid_visual_json", "Inspect P&ID visual JSON when graph evidence lacks required safety devices.", args, "low"))

    debug = dict(evidence_data.get("debug", {}) or {})
    debug.update(
        {
            "planner_code_version": "local_deterministic_planner_2026-08-18_v2",
            "planner_mode": "deterministic_graph_api_evidence_checks",
            "planner_required_evidence_check_count": len(checks),
            "planner_required_evidence_checks": [check["check_name"] for check in checks],
        }
    )
    return {
        **evidence_data,
        "debug": debug,
        "required_evidence_checks": checks,
        "planner_state": {
            "mode": "deterministic_graph_api_evidence_checks",
            "required_evidence_checks": checks,
        },
    }


def _check(check_name, reason, arguments, priority, evidence_targets=None):
    targets = evidence_targets or []
    return {
        "check_name": check_name,
        "priority": priority,
        "reason": reason,
        "arguments": arguments,
        "status": "required",
        "source": "deterministic_rule",
        "drawing_binding_status": "candidates_found" if targets else "no_drawing_candidate",
        "evidence_targets": targets,
    }


def _relief_targets(data):
    targets = []
    for item in ((data.get("relief_candidates") or {}).get("items") or []):
        entity_id = str(item.get("id") or "").strip()
        if not entity_id:
            continue
        targets.append(
            {
                "entity_id": entity_id,
                "entity_type": item.get("entity_type"),
                "entity_class": item.get("entity_class"),
                "tag": item.get("tag"),
                "bbox": item.get("bbox") or [],
                "role": "stored_energy_release_candidate",
                "basis": item.get("basis") or "Deterministically identified relief candidate.",
                "acceptance": "field_confirmation_required",
                "path_node_ids": [],
            }
        )
    known = {target["entity_id"] for target in targets}
    targets.extend(target for target in _terminal_release_targets(data) if target["entity_id"] not in known)
    return targets


def _terminal_release_targets(data):
    """Locate branch valves leading to an exact terminal end as review candidates.

    A terminal branch can be a drain/bleed, but a flange can also be a future
    connection. It is therefore surfaced for field confirmation and never accepted
    automatically as stored-energy relief.
    """
    payload = data.get("_hilt_payload") or {}
    graph = payload.get("hilt_graph") if isinstance(payload, dict) else None
    if not isinstance(graph, dict):
        return []
    nodes = {}
    for node in graph.get("nodes") or []:
        raw = node.get("payload") or {}
        node_id = str(node.get("id") or raw.get("id") or raw.get("source_id") or "").strip()
        if node_id:
            nodes[node_id] = raw
    adjacency = {}
    for link in graph.get("links") or []:
        raw = link.get("payload") or {}
        if str(raw.get("entity_type") or "").lower() != "process_line":
            continue
        source = str(link.get("source") or raw.get("from") or "").strip()
        target = str(link.get("target") or raw.get("to") or "").strip()
        if source and target:
            adjacency.setdefault(source, set()).add(target)
            adjacency.setdefault(target, set()).add(source)

    terminal_classes = {"flanged_end", "open_end", "open_vent", "atmosphere"}
    targets = []
    for candidate in data.get("candidates") or []:
        path = [str(value) for value in candidate.get("branch_path_node_ids") or [] if value]
        classes = {str(value or "").lower() for value in candidate.get("branch_path_node_classes") or []}
        if not ({"tee", "junction"} & classes):
            continue
        candidate_id = str(candidate.get("visual_node_id") or candidate.get("visual_id") or candidate.get("candidate_id") or "").strip()
        if not candidate_id or candidate_id not in nodes:
            continue
        previous = path[-2] if len(path) > 1 and path[-1] == candidate_id else ""
        queue = [(candidate_id, 0, [candidate_id])]
        seen = {candidate_id, previous}
        terminal_path = None
        while queue:
            node_id, depth, current_path = queue.pop(0)
            if depth > 0 and str(nodes.get(node_id, {}).get("entity_class") or "").lower() in terminal_classes:
                terminal_path = current_path
                break
            if depth >= 2:
                continue
            for neighbor in sorted(adjacency.get(node_id, ())):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append((neighbor, depth + 1, current_path + [neighbor]))
        if not terminal_path:
            continue
        node = nodes[candidate_id]
        text = [str(item.get("value") or "").strip() for item in node.get("text") or [] if isinstance(item, dict) and item.get("value")]
        targets.append(
            {
                "entity_id": candidate_id,
                "entity_type": node.get("entity_type"),
                "entity_class": node.get("entity_class"),
                "tag": " ".join(text) or candidate.get("tag_number"),
                "bbox": candidate.get("bbox") or [],
                "role": "potential_stored_energy_release_branch",
                "basis": "Valve lies on an exact HILT branch ending at a terminal/flanged end; confirm that it is an approved drain or bleed with a safe discharge destination.",
                "acceptance": "function_and_safe_discharge_confirmation_required",
                "path_node_ids": terminal_path,
            }
        )
    return targets


def _pressure_targets(data):
    targets = []
    for item in ((data.get("instrument_context") or {}).get("instruments") or []):
        if str(item.get("measured_variable") or "").lower() != "pressure":
            continue
        if "verification_support" not in set(item.get("sop_uses") or []):
            continue
        if item.get("entity_type") != "instrument":
            continue
        entity_id = str(item.get("id") or "").strip()
        if not entity_id:
            continue
        targets.append(
            {
                "entity_id": entity_id,
                "entity_type": item.get("entity_type"),
                "entity_class": item.get("entity_class"),
                "tag": item.get("tag"),
                "bbox": item.get("bbox") or [],
                "role": "zero_energy_verification_support",
                "basis": item.get("verification_note") or item.get("relevance_basis"),
                "acceptance": "approved_method_confirmation_required",
                "path_node_ids": [],
            }
        )
    return targets


def _topology_review_targets(data):
    targets = []
    for item in ((data.get("isolation_obligations") or {}).get("items") or []):
        path = [str(value) for value in item.get("branch_path_node_ids") or [] if value]
        if item.get("source_type") != "process" or item.get("status") != "isolated" or not path:
            continue
        targets.append(
            {
                "entity_id": path[-1],
                "entity_type": "topology_path",
                "entity_class": "isolation_branch",
                "tag": item.get("source_component_tag"),
                "bbox": [],
                "role": "bypass_review_path",
                "basis": "Known covered HILT process branch requiring alternate-route review.",
                "acceptance": "topology_review_required",
                "path_node_ids": path,
            }
        )
    return targets
