from gremlin_python.process.graph_traversal import __

from domain.classification import classify_candidate
from domain.enums import IsolationDecision
from graph_client import GraphClient, normalize_vertex, props_only, vertex_id, vertex_label


def fetch_boundaries(config):
    with GraphClient(config.graph) as client:
        g = client.g
        equipment_rows = (
            _fetch_selected_equipment_vertices(g, config.selected_asset.hilt_entity_id)
            if config.selected_asset is not None
            else _fetch_equipment_vertices(g, config.equipment_tag)
        )
        equipment_vertices = _dedupe_vertices(normalize_vertex(row) for row in equipment_rows)
        equipment_vertices, target_identity = _verify_selected_asset(equipment_vertices, config.selected_asset)
        equipment_results = []
        traversal_limit_hit = False

        for equipment in equipment_vertices:
            equipment_id = vertex_id(equipment)
            component_rows = (
                g.V(equipment_id)
                .out("PHYSICALLY_HAS_A")
                .hasLabel("Component")
                .valueMap(True)
                .toList()
            )
            components = [normalize_vertex(row) for row in component_rows]
            edge_labels = g.V(equipment_id).bothE().label().dedup().toList()
            component_boundaries = []

            for component in components:
                boundary, hit_limit = _component_boundary(
                    g,
                    component,
                    config.policy,
                    getattr(config, "approved_corrections", ()) or (),
                )
                traversal_limit_hit = traversal_limit_hit or hit_limit
                component_boundaries.append(boundary)

            equipment_results.append(
                {
                    "equipment": {
                        "id": equipment_id,
                        "label": vertex_label(equipment),
                        "properties": props_only(equipment),
                    },
                    "edge_labels": edge_labels,
                    "components": [
                        {
                            "id": vertex_id(component),
                            "label": vertex_label(component),
                            "properties": props_only(component),
                        }
                        for component in components
                    ],
                    "component_boundaries": component_boundaries,
                }
            )

    return {
        "error": False,
        "target_mode": "selected_equipment",
        "requested_equipment_tags": [config.equipment_tag],
        "matched_equipment_count": len(equipment_results),
        "max_traversal_depth": config.policy.max_traversal_depth,
        "traversal_limit_hit": traversal_limit_hit,
        "equipment_boundaries": equipment_results,
        "target_identity": target_identity,
        "context": config.context,
    }


def _verify_selected_asset(equipment_vertices, selected_asset):
    """Resolve exact HILT identity against one graph equipment vertex.

    Tag matching discovers a bounded set for legacy compatibility, but never
    proves identity. Browser selections must match an explicit source identity
    property on exactly one vertex.
    """
    if selected_asset is None:
        return equipment_vertices, {
            "status": "legacy_tag_only",
            "identity_quality": "legacy_tag_only",
            "tag": "",
        }

    wanted = str(selected_asset.hilt_entity_id)
    matches = []
    matched_properties = []
    for vertex in equipment_vertices:
        properties = props_only(vertex)
        for property_name in ("node_id", "cnvrt_id", "source_id", "uuid"):
            if str(properties.get(property_name) or "").strip() == wanted:
                matches.append(vertex)
                matched_properties.append(property_name)
                break

    if len(matches) != 1:
        reason = "not_found" if not matches else "ambiguous"
        raise RuntimeError(
            f"Selected HILT equipment identity could not be verified: {reason} "
            f"for job {selected_asset.context.job_id}."
        )

    vertex = matches[0]
    return matches, {
        "status": "verified",
        "identity_quality": "exact",
        "selection_source": selected_asset.selection_source.value,
        "tag": selected_asset.tag,
        "hilt_entity_id": wanted,
        "hilt_entity_class": selected_asset.hilt_entity_class,
        "unigraph_vertex_id": str(vertex_id(vertex)),
        "unigraph_identity_property": matched_properties[0],
        "unigraph_project_id": selected_asset.context.unigraph_project_id,
        "job_id": selected_asset.context.job_id,
    }


def _fetch_selected_equipment_vertices(g, hilt_entity_id):
    """Fetch by source identity only; tags deliberately do not participate."""
    return (
        g.V()
        .hasLabel("Equipment")
        .or_(
            __.has("node_id", hilt_entity_id),
            __.has("cnvrt_id", hilt_entity_id),
            __.has("source_id", hilt_entity_id),
            __.has("uuid", hilt_entity_id),
        )
        .valueMap(True)
        .toList()
    )


def _fetch_equipment_vertices(g, equipment_tag):
    rows = (
        g.V()
        .hasLabel("Equipment")
        .or_(
            __.has("tag", equipment_tag),
            __.has("tag_number", equipment_tag),
            __.has("Equipment Name", equipment_tag),
            __.has("name", equipment_tag),
        )
        .valueMap(True)
        .toList()
    )
    if rows:
        return rows

    requested_key = _tag_key(equipment_tag)
    if not requested_key:
        return rows
    fallback_rows = g.V().hasLabel("Equipment").valueMap(True).toList()
    return [
        row
        for row in fallback_rows
        if requested_key
        in {
            _tag_key(_raw_property(row, "tag")),
            _tag_key(_raw_property(row, "tag_number")),
            _tag_key(_raw_property(row, "Equipment Name")),
            _tag_key(_raw_property(row, "name")),
            _tag_key(_raw_property(row, "equipment_number")),
        }
    ]


def _raw_property(row, key):
    value = row.get(key)
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def _tag_key(value):
    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _dedupe_vertices(vertices):
    seen = set()
    result = []
    for vertex in vertices:
        key = vertex_id(vertex)
        if key in seen:
            continue
        seen.add(key)
        result.append(vertex)
    return result


def _component_boundary(g, component, policy, corrections=()):
    component_id = vertex_id(component)
    component_edge_labels = g.V(component_id).bothE().label().dedup().toList()
    component_neighbors = (
        g.V(component_id)
        .both(*policy.candidate_edge_labels)
        .dedup()
        .limit(policy.traversal_limit_per_depth)
        .valueMap(True)
        .toList()
    )
    component_neighbors = [normalize_vertex(row) for row in component_neighbors]

    unavailable_identities = _final_unavailable_identities(corrections)

    def expand(vertex_ids):
        if not vertex_ids:
            return {}
        rows = (
            g.V(*vertex_ids)
            .as_("origin")
            .bothE(*policy.candidate_edge_labels)
            .as_("edge")
            .otherV()
            .hasLabel("Component")
            .as_("target")
            .select("origin", "edge", "target")
            .by(__.id_())
            .by(__.label())
            .by(__.valueMap(True))
            .toList()
        )
        adjacency = {str(value): [] for value in vertex_ids}
        for row in rows:
            target = normalize_vertex(row.get("target") or {})
            adjacency.setdefault(str(row.get("origin")), []).append(
                {"vertex": target, "edge_label": str(row.get("edge") or "")}
            )
        return adjacency

    traversal_sample, graph_branches, limit_hit = _walk_component_topology(
        component_id,
        expand,
        policy,
        unavailable_identities,
    )

    return (
        {
            "component": {
                "id": component_id,
                "label": vertex_label(component),
                "properties": props_only(component),
            },
            "edge_labels": component_edge_labels,
            "direct_neighbors": [
                {
                    "id": vertex_id(vertex),
                    "label": vertex_label(vertex),
                    "properties": props_only(vertex),
                    "traversal_depth": 1,
                }
                for vertex in component_neighbors
            ],
            "traversal_sample": traversal_sample,
            "graph_branches": graph_branches,
        },
        limit_hit,
    )


def _walk_component_topology(start_id, expand, policy, unavailable_identities=()):
    """Cycle-safe, path-preserving BFS over UniGraph component connectivity.

    Each path stops at its first usable barrier. An unavailable barrier is
    retained for audit but treated as pass-through. Limits are fail-safe:
    unfinished paths are returned as unresolved rather than silently accepted.
    """
    start = str(start_id)
    frontier = [{"current": start, "path": (start,), "edges": ()}]
    samples = []
    branches = []
    limit_hit = False

    for depth in range(1, int(policy.max_traversal_depth) + 1):
        if not frontier:
            break
        adjacency = expand([state["current"] for state in frontier])
        next_frontier = []
        for state in frontier:
            neighbors = [
                item
                for item in adjacency.get(str(state["current"]), [])
                if str(vertex_id(item["vertex"])) not in state["path"]
            ]
            if not neighbors:
                if len(state["path"]) > 1:
                    branches.append(_graph_branch(state["path"], state["edges"], "unresolved", reason="terminal_without_barrier"))
                continue
            for item in neighbors:
                vertex = item["vertex"]
                target_id = str(vertex_id(vertex))
                path = (*state["path"], target_id)
                edges = (*state["edges"], item.get("edge_label") or "")
                selectable = _selectable_barrier_vertex(vertex, policy)
                unavailable = selectable and _vertex_matches_identities(vertex, unavailable_identities)
                sample = {
                    "id": vertex_id(vertex),
                    "label": vertex_label(vertex),
                    "properties": props_only(vertex),
                    "traversal_depth": depth,
                    "graph_path_ids": list(path),
                    "graph_path_edge_labels": list(edges),
                    "graph_path_key": ">".join(path),
                    "graph_path_status": "unavailable_pass_through" if unavailable else "barrier" if selectable else "transit",
                    "graph_path_complete": bool(selectable and not unavailable),
                }
                if unavailable:
                    sample.update(availability_status="unavailable", available_for_isolation=False)
                samples.append(sample)
                if selectable and not unavailable:
                    branches.append(_graph_branch(path, edges, "isolated", barrier_id=target_id))
                else:
                    next_frontier.append({"current": target_id, "path": path, "edges": edges})

        if len(next_frontier) > int(policy.traversal_limit_per_depth):
            limit_hit = True
            next_frontier = next_frontier[: int(policy.traversal_limit_per_depth)]
        # Exact path dedupe prevents duplicate Gremlin edges from multiplying a
        # state while retaining distinct split paths and reconvergence evidence.
        frontier = list({state["path"]: state for state in next_frontier}.values())

    if frontier:
        limit_hit = True
        branches.extend(
            _graph_branch(state["path"], state["edges"], "unresolved", reason="safety_limit_reached")
            for state in frontier
        )
    return samples, _dedupe_graph_branches(branches), limit_hit


def _selectable_barrier_vertex(vertex, policy):
    classification = classify_candidate(props_only(vertex), vertex_label(vertex), policy)
    return classification.decision in {
        IsolationDecision.AUTOMATIC,
        IsolationDecision.CONDITIONAL_MANUAL_REVIEW,
    }


def _vertex_matches_identities(vertex, identities):
    properties = props_only(vertex)
    values = {str(vertex_id(vertex))}
    values.update(
        str(properties.get(key) or "").strip()
        for key in ("node_id", "source_id", "uuid", "cnvrt_id")
    )
    return bool(values.intersection(identities))


def _final_unavailable_identities(corrections):
    unavailable = set()
    for correction in corrections or ():
        kind = str(correction.get("change_type") or "")
        if kind not in {"mark_point_unavailable", "mark_point_available"}:
            continue
        proposed = correction.get("proposed_change") or {}
        identities = {
            str(correction.get("target_id") or "").strip(),
            str(proposed.get("drawing_entity_id") or "").strip(),
        }
        identities.discard("")
        if kind == "mark_point_unavailable":
            unavailable.update(identities)
        else:
            unavailable.difference_update(identities)
    return unavailable


def _graph_branch(path, edges, status, *, barrier_id="", reason=""):
    return {
        "branch_id": "unigraph:" + ">".join(path),
        "path_node_ids": list(path),
        "path_edge_labels": list(edges),
        "status": status,
        "barrier_id": barrier_id,
        "reason": reason,
    }


def _dedupe_graph_branches(branches):
    result = {}
    for branch in branches:
        key = (tuple(branch.get("path_node_ids") or ()), branch.get("status"), branch.get("barrier_id"))
        result[key] = branch
    return list(result.values())
