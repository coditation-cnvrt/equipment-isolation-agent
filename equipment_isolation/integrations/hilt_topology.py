"""HILT-topology isolation resolver.

The HILT graph (cnvrt-backend-api) is the parsed P&ID piping network: nodes
(nozzles, valves, junctions, equipment) connected by process-line links. This is
the AUTHORITATIVE source for "which valve is physically piped to which nozzle" --
far more trustworthy than JanusGraph traversal depth + bbox distance, which can
pick a geographically-near but topologically-wrong valve.

For each equipment nozzle we walk the process-line graph and find the FIRST valve
on each branch (valves are treated as leaves -- the nearest valve on a branch is
the isolation point for that branch). Returns nozzle -> [valves] with HILT bboxes.
"""
from __future__ import annotations

from collections import deque

from equipment_isolation.domain.classification import class_matches, classify_candidate, normalize_class
from equipment_isolation.domain.enums import IsolationDecision
from equipment_isolation.domain.topology import PROCESS_LINE_CLASSES, normalize_tag, nozzle_belongs_to_equipment
from equipment_isolation.integrations.hilt_index import _hilt_path_link_summary

BRANCH_CONTEXT_VALVE_CLASSES = {"check_valve", "control_valve"}
# Plain flanges are connection hardware, not deterministic barriers. They remain
# fallback field-confirmation candidates elsewhere, but authoritative topology
# must continue through them to find an actual valve/blind/disconnection.
TRAVERSABLE_CONNECTION_CLASSES = {"flange", "flanged_joint"}


def resolve_nozzle_isolation(hilt_payload: dict, equipment_tag: str, y_flip: float | None = None, policy=None, unavailable_ids=None) -> dict:
    """Walk the HILT piping graph to find the valve isolating each equipment nozzle.

    ``y_flip`` is the image-height constant H such that image_y = H - hilt_y (HILT
    uses a CAD bottom-left origin; the P&ID image uses a top-left origin). When
    provided, valve bboxes are flipped into image coordinates. Calibrate H per job
    by matching HILT nozzles to STLM nozzles (STLM coords are already image-space).
    """
    graph = hilt_payload.get("hilt_graph") if isinstance(hilt_payload, dict) else None
    if not isinstance(graph, dict):
        return {}
    nodes = graph.get("nodes") or []
    node_by_id, adj = _hilt_index(graph)

    eq_norm = _norm(equipment_tag)
    nozzles: dict[str, str] = {}  # tag -> node_id
    for node in nodes:
        payload = node.get("payload") or {}
        if payload.get("entity_class") != "equipment_nozzle":
            continue
        tag = _attr(payload.get("attributes"), "tag")
        if tag and eq_norm and nozzle_belongs_to_equipment(tag, equipment_tag):
            nid = node.get("id") or payload.get("id")
            if nid:
                nozzles[str(tag)] = str(nid)

    result: dict[str, list] = {}
    for tag, nozzle_id in nozzles.items():
        result[tag] = _nearest_valves(
            nozzle_id, adj, node_by_id, max_hops=24, y_flip=y_flip,
            policy=policy, unavailable_ids=unavailable_ids,
        )
    return result


def resolve_source_branch_isolation(
    hilt_payload: dict,
    source_entries: list[dict],
    y_flip: float | None = None,
    policy=None,
    max_hops: int = 24,
    unavailable_ids=None,
) -> list[dict]:
    """Resolve required isolation per process branch from concrete HILT source UUIDs.

    A source is an equipment connection/nozzle already matched between UniGraph/STLM
    and HILT. This path is more reliable for Aker-style drawings where equipment
    nozzles are present but not tagged with the equipment name.
    """
    graph = hilt_payload.get("hilt_graph") if isinstance(hilt_payload, dict) else None
    if not isinstance(graph, dict):
        return []
    node_by_id, adj = _hilt_index(graph)
    results = []
    seen_sources = set()
    for source in source_entries or []:
        if source.get("source_context_type") or source.get("source_type") == "instrument_context":
            continue
        source_visual_id = str(source.get("source_visual_id") or source.get("source_visual_node_id") or "").strip()
        if not source_visual_id or source_visual_id not in node_by_id or source_visual_id not in adj:
            continue
        source_component = str(source.get("source_component_id") or source.get("source_component_tag") or "").strip()
        equipment_tag = str(source.get("equipment_tag") or "").strip()
        source_key = (equipment_tag, source_component, source_visual_id)
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)
        branches = _nearest_branch_devices(
            source_visual_id,
            adj,
            node_by_id,
            max_hops=max_hops,
            y_flip=y_flip,
            policy=policy,
            unavailable_ids=unavailable_ids,
        )
        if not branches:
            continue
        for index, branch in enumerate(branches, start=1):
            branch["branch_index"] = index
            branch["branch_id"] = f"{source_component or source_visual_id}:branch:{index}"
        results.append(
            {
                "equipment_tag": equipment_tag,
                "source_component": source_component,
                "source_component_tag": str(source.get("source_component_tag") or source_component),
                "source_visual_id": source_visual_id,
                "source_bbox": source.get("source_bbox") or [],
                "branches": branches,
            }
        )
    return results


def _hilt_index(graph):
    nodes = graph.get("nodes") or []
    links = graph.get("links") or []
    node_by_id: dict[str, dict] = {}
    for node in nodes:
        nid = node.get("id") or (node.get("payload") or {}).get("id")
        if nid:
            node_by_id[str(nid)] = node

    # Build the process network first. A HILT ``companion_line`` is normally
    # non-process context and must not be generally traversable. Some equipment
    # symbols, however, use one companion edge purely as the graphical attachment
    # from an equipment nozzle to a split flange whose other side starts the real
    # process line. Admit only that narrow nozzle->process-network bridge.
    adj: dict[str, list[dict]] = {}
    companion_links = []
    for link in links:
        payload = link.get("payload") or {}
        source = str(link.get("source") or payload.get("from") or "")
        target = str(link.get("target") or payload.get("to") or "")
        if not source or not target:
            continue
        entity_class = normalize_class(payload.get("entity_class"))
        if entity_class in PROCESS_LINE_CLASSES:
            _append_edge(adj, source, target, link)
        elif entity_class == "companion_line":
            companion_links.append((source, target, link))

    process_nodes = set(adj)
    for source, target, link in companion_links:
        source_class = normalize_class(_node_class(source, node_by_id))
        target_class = normalize_class(_node_class(target, node_by_id))
        if source_class == "equipment_nozzle" and target in process_nodes:
            _append_edge(adj, source, target, link)
        elif target_class == "equipment_nozzle" and source in process_nodes:
            _append_edge(adj, source, target, link)
    return node_by_id, adj


def _append_edge(adj, source, target, link):
    facts = _hilt_path_link_summary(link)
    adj.setdefault(source, []).append(
        {"node_id": target, "link": {**facts, "from_node_id": source, "to_node_id": target}}
    )
    adj.setdefault(target, []).append(
        {"node_id": source, "link": {**facts, "from_node_id": target, "to_node_id": source}}
    )


def _nearest_valves(start, adj, node_by_id, max_hops, y_flip=None, policy=None, unavailable_ids=None):
    return [
        branch["valve"]
        for branch in _nearest_branch_devices(
            start, adj, node_by_id, max_hops=max_hops, y_flip=y_flip,
            policy=policy, unavailable_ids=unavailable_ids,
        )
        if branch.get("status") == "isolated" and branch.get("valve")
    ]


def _nearest_branch_devices(start, adj, node_by_id, max_hops, y_flip=None, policy=None, unavailable_ids=None):
    """BFS from a nozzle over process lines; record the first valve on each branch.
    Valves are leaves (we do not traverse through them) -- the nearest valve on a
    branch is that branch's isolation point."""
    if getattr(policy, 'process_safety_inputs', None) is not None:
        return _configuration_candidate_branches(start, adj, node_by_id, max_hops, y_flip, policy, unavailable_ids)
    unavailable = {str(value) for value in (unavailable_ids or ()) if value not in (None, "")}
    queue = deque([(start, 0, [start], [], [])])
    found: list[dict] = []
    cycles: list[dict] = []
    while queue:
        node, hops, path, path_links, context_devices = queue.popleft()
        if hops >= max_hops:
            found.append(_unresolved_branch(path, path_links, context_devices, "max_hops_reached", node_by_id))
            continue
        expanded = False
        neighbors = sorted(
            adj.get(node, ()),
            key=lambda item: (
                str(item.get("node_id") or ""),
                str((item.get("link") or {}).get("line_id") or ""),
            ),
        )
        for edge in neighbors:
            nbr = str(edge.get("node_id") or "")
            if not nbr:
                continue
            if nbr in path:
                # Skip the incoming edge; retain a distinct cycle-closing edge.
                if path_links and _path_edge_key(edge.get("link") or {}) == _path_edge_key(path_links[-1]):
                    continue
                cycles.append(_unresolved_branch(
                    path + [nbr], path_links + [edge.get("link") or {}],
                    context_devices, "cycle_without_demonstrated_barrier", node_by_id,
                ))
                continue
            new_path = path + [nbr]
            new_path_links = path_links + [edge.get("link") or {}]
            expanded = True
            branch_role = _branch_device_role(nbr, node_by_id, policy)
            if branch_role == "required_isolation":
                if nbr in unavailable:
                    unavailable_device = _valve_summary(nbr, node_by_id, hops + 1, new_path, y_flip)
                    unavailable_device.update(
                        availability_status="unavailable",
                        available_for_isolation=False,
                        reason="Approved correction reports this device faulty or out of service; traversal continued to seek an alternate barrier.",
                    )
                    queue.append((nbr, hops + 1, new_path, new_path_links, context_devices + [unavailable_device]))
                    continue
                found.append(
                    {
                        "status": "isolated",
                        "valve": _valve_summary(nbr, node_by_id, hops + 1, new_path, y_flip),
                        "path_node_ids": new_path,
                        "path_node_classes": [_node_class(node_id, node_by_id) for node_id in new_path],
                        "path_link_ids": [str(link.get("line_id") or "") for link in new_path_links],
                        "path_link_facts": new_path_links,
                        "context_devices": context_devices,
                        "basis": "first required isolation device on HILT process branch",
                    }
                )
                # valves are leaves -- do not traverse past the isolation point
                continue
            next_context = context_devices
            if branch_role == "backflow_or_control_context":
                next_context = context_devices + [_valve_summary(nbr, node_by_id, hops + 1, new_path, y_flip)]
            queue.append((nbr, hops + 1, new_path, new_path_links, next_context))
        distinct_neighbor_ids = {str(item.get("node_id") or "") for item in neighbors}
        if not expanded and node != start and len(distinct_neighbor_ids) <= 1:
            found.append(
                _unresolved_branch(
                    path,
                    path_links,
                    context_devices,
                    "no_required_isolation_device_found",
                    node_by_id,
                )
            )
    represented_edges = {
        _path_edge_key(link) for branch in found for link in branch.get("path_link_facts") or []
    }
    seen_cycles = set()
    for cycle in cycles:
        edges = frozenset(_path_edge_key(link) for link in cycle["path_link_facts"])
        if not edges.issubset(represented_edges) and edges not in seen_cycles:
            found.append(cycle)
            seen_cycles.add(edges)
    found.sort(
        key=lambda item: (
            0 if item.get("status") == "isolated" else 1,
            int(((item.get("valve") or {}).get("hop_distance") or len(item.get("path_node_ids") or []))),
            str((item.get("valve") or {}).get("valve_id") or item.get("branch_id") or ""),
            tuple(item.get("path_link_ids") or ()),
        )
    )
    return _dedupe_branches(found)


def _path_edge_key(link):
    return (str(link.get("line_id") or ""), tuple(sorted((
        str(link.get("from_node_id") or link.get("source") or ""),
        str(link.get("to_node_id") or link.get("target") or ""),
    ))))


def _valve_summary(valve_id: str, node_by_id: dict, hop_distance: int, path, y_flip: float | None = None) -> dict:
    node = node_by_id.get(valve_id) or {}
    payload = node.get("payload") or {}
    return {
        "valve_id": valve_id,
        "entity_class": payload.get("entity_class"),
        "entity_type": payload.get("entity_type"),
        "tag": _attr(payload.get("attributes"), "tag"),
        "bbox": _hilt_bbox(payload, y_flip),
        "hop_distance": hop_distance,
        "path_node_count": len(path),
        "path_node_ids": list(path),
        "connectivity_source": "hilt_topology",
    }


def _unresolved_branch(path, path_links, context_devices, reason, node_by_id):
    terminal_id = str(path[-1]) if path else ""
    return {
        "status": "unresolved",
        "valve": None,
        "path_node_ids": list(path),
        "path_node_classes": [_node_class(node_id, node_by_id) for node_id in path],
        "path_link_ids": [str(link.get("line_id") or "") for link in path_links],
        "path_link_facts": list(path_links),
        "context_devices": context_devices,
        "terminal_node": _terminal_node_summary(terminal_id, node_by_id),
        "basis": reason,
    }


def _dedupe_branches(branches):
    result = []
    seen = set()
    for branch in branches:
        key = (
            branch.get("status"),
            tuple(branch.get("path_node_ids") or ()),
            tuple(branch.get("path_link_ids") or ()),
            str((branch.get("valve") or {}).get("valve_id") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(branch)
    return result


def _terminal_node_summary(node_id, node_by_id):
    payload = (node_by_id.get(str(node_id)) or {}).get("payload") or {}
    partner = payload.get("partner_opc") if isinstance(payload.get("partner_opc"), dict) else {}
    return {
        "entity_id": str(payload.get("id") or node_id or ""),
        "entity_type": payload.get("entity_type"),
        "entity_class": payload.get("entity_class"),
        "tag": _attr(payload.get("attributes"), "tag"),
        # Text is display context only. It is never used to establish an OPC edge.
        "display_text": [
            str(item.get("value"))
            for item in payload.get("text") or []
            if isinstance(item, dict) and item.get("value") not in (None, "")
        ],
        "partner_opc": {
            key: str(partner.get(key) or "").strip()
            for key in ("id", "job_id", "job_name", "opc_name")
        },
    }


def _branch_device_role(node_id, node_by_id, policy):
    node = node_by_id.get(str(node_id)) or {}
    payload = node.get("payload") or {}
    entity_class = payload.get("entity_class")
    if normalize_class(entity_class) in TRAVERSABLE_CONNECTION_CLASSES:
        return "traversable"
    if _is_branch_context_device(entity_class):
        return "backflow_or_control_context"
    if policy is None:
        return "required_isolation" if "valve" in str(entity_class or "").lower() else "traversable"
    classification = classify_candidate({"entity_class": entity_class, "entity_type": payload.get("entity_type")}, entity_class, policy)
    if classification.decision in {IsolationDecision.AUTOMATIC, IsolationDecision.CONDITIONAL_MANUAL_REVIEW}:
        return "required_isolation"
    return "traversable"


def _is_branch_context_device(entity_class):
    normalized = normalize_class(entity_class)
    return any(class_matches(normalized, value) for value in BRANCH_CONTEXT_VALVE_CLASSES)


def _node_class(node_id, node_by_id):
    return (node_by_id.get(str(node_id)) or {}).get("payload", {}).get("entity_class")


def _hilt_bbox(payload: dict, y_flip: float | None = None) -> list:
    location = payload.get("bounding_box_location") or {}
    width = payload.get("bounding_box_width")
    height = payload.get("bounding_box_height")
    if location.get("x") is None or location.get("y") is None or width is None or height is None:
        return []
    cx = float(location.get("x"))
    cy = float(location.get("y"))
    w = float(width)
    h = float(height)
    x = cx - w / 2.0
    y = (y_flip - cy - h / 2.0) if y_flip is not None else (cy - h / 2.0)
    return [int(round(x)), int(round(y)), int(round(w)), int(round(h))]


def _attr(attributes, name):
    target = str(name or "").strip().lower()
    for attr in attributes or []:
        if isinstance(attr, dict) and str(attr.get("name") or "").strip().lower() == target:
            value = attr.get("value")
            if value not in (None, "", []):
                return str(value)
    return None


# Alias, not a wrapper: normalize_tag is the single implementation.
_norm = normalize_tag


def _configuration_candidate_branches(start, adj, node_by_id, max_hops, y_flip, policy, unavailable_ids):
    """Search outward for path-local candidate configurations, never certify them.

    Counts are a search criterion only. Lockability, ratings, disconnection and
    bleed destination still require evidence in the process safety validator.
    """
    from equipment_isolation.domain.process_safety import required_configuration_for_path
    unavailable = {str(x) for x in unavailable_ids or ()}
    queue = deque([(start, [start], [], [])])
    found, expanded_count = [], 0
    while queue:
        node, path, links, devices = queue.popleft()
        def finish(reason):
            branch = _unresolved_branch(path, links, devices, reason, node_by_id)
            branch['barrier_candidates'] = devices
            found.append(branch)
        if len(links) >= max_hops:
            finish('safety_limit_reached'); continue
        neighbors = sorted(adj.get(node, ()), key=lambda edge: (str(edge.get('node_id')), str(edge.get('link', {}).get('line_id'))))
        choices = [edge for edge in neighbors if not links or _path_edge_key(edge.get('link') or {}) != _path_edge_key(links[-1])]
        if not choices:
            finish('configuration_not_found_before_terminal'); continue
        for edge in choices:
            expanded_count += 1
            if expanded_count > 2000:
                finish('safety_limit_reached')
                return found
            neighbor = str(edge.get('node_id') or '')
            new_path, new_links = path + [neighbor], links + [edge.get('link') or {}]
            if neighbor in path:
                branch = _unresolved_branch(new_path, new_links, devices, 'cycle_without_demonstrated_configuration', node_by_id)
                branch['barrier_candidates'] = devices; found.append(branch); continue
            kind = normalize_class(_node_class(neighbor, node_by_id))
            next_devices = list(devices)
            if _branch_device_role(neighbor, node_by_id, policy) == 'required_isolation' and neighbor not in unavailable:
                # Spectacle-open symbols are not a demonstrated positive closure.
                summary = _valve_summary(neighbor, node_by_id, len(new_links), new_path, y_flip)
                summary['positive_candidate'] = kind in {'blind', 'spade', 'blank_flange', 'blind_flange'}
                next_devices.append(summary)
                required = required_configuration_for_path({'path_link_facts': new_links}, policy.process_safety_inputs)
                if len(next_devices) >= required['barrier_count'] and sum(d['positive_candidate'] for d in next_devices) >= required['positive_barrier_count']:
                    branch = _unresolved_branch(new_path, new_links, [], 'candidate_configuration_requires_validation', node_by_id)
                    branch['barrier_candidates'] = next_devices
                    branch['required_configuration'] = required
                    found.append(branch)
                    continue
            if kind == 'equipment_nozzle' and neighbor != start:
                branch = _unresolved_branch(new_path, new_links, [], 'other_equipment_boundary_configuration_unresolved', node_by_id)
                branch['barrier_candidates'] = next_devices; found.append(branch); continue
            queue.append((neighbor, new_path, new_links, next_devices))
    return found
