"""Targeted graph resolution for approved manual isolation-point additions."""
from __future__ import annotations

from gremlin_python.process.graph_traversal import __
from gremlin_python.process.traversal import T

from equipment_isolation.core.candidates import candidate_from_exact_correction_target, _dedupe_candidates
from equipment_isolation.integrations.graph_client import GraphClient, normalize_vertex, props_only, vertex_id, vertex_label


TARGET_LOOKUP_MAX_DEPTH = 12
TARGET_LOOKUP_MAX_EDGES = 5000
_IDENTITY_PROPERTIES = ("node_id", "cnvrt_id", "source_id", "uuid")


def enrich_approved_correction_targets(candidate_data: dict, boundary_data: dict, config) -> dict:
    additions = [
        correction
        for correction in (getattr(config, "approved_corrections", ()) or ())
        if str(correction.get("change_type") or "") == "add_manual_isolation_point"
    ]
    if not additions:
        return candidate_data

    pool = list(candidate_data.get("_candidate_pool") or [])
    resolutions = list(candidate_data.get("correction_target_resolution") or [])
    sources = _boundary_sources(boundary_data)

    for correction in additions:
        target_id = str(correction.get("target_id") or "").strip()
        change_id = str(correction.get("change_id") or "")
        if _pool_has_identity(pool, target_id):
            resolutions.append(_resolution(change_id, target_id, "resolved", "Target was already present in the automatic candidate pool."))
            continue
        if not sources:
            resolutions.append(_resolution(change_id, target_id, "failed", "No equipment boundary sources were available for exact-target lookup."))
            continue

        lookup = _resolve_target_from_graph(
            config.graph,
            target_id,
            set(sources),
            config.policy.candidate_edge_labels,
        )
        if lookup["status"] != "resolved":
            resolutions.append(_resolution(change_id, target_id, lookup["status"], lookup["reason"]))
            continue

        records = []
        for source_id in lookup["source_ids"]:
            source = sources[source_id]
            candidate = candidate_from_exact_correction_target(
                source["equipment_tag"],
                source["component"],
                lookup["vertex"],
                lookup["depth"],
                config.policy,
            )
            if candidate:
                candidate["correction_lookup_path_vertex_ids"] = lookup["paths"].get(source_id) or []
                records.append(candidate)
        if not records:
            reason = "The exact graph target was found, but its class is not eligible for isolation-point evaluation."
            resolutions.append(_resolution(change_id, target_id, "failed", reason))
            continue

        resolved = _dedupe_candidates(records)
        pool.extend(resolved)
        resolutions.append(_resolution(
            change_id,
            target_id,
            "resolved",
            f"Exact target resolved at {lookup['depth']} hops from {len(lookup['source_ids'])} boundary source(s).",
        ))

    result = dict(candidate_data)
    result["_candidate_pool"] = pool
    result["correction_target_resolution"] = resolutions
    debug = dict(result.get("debug") or {})
    debug["candidate_pool_count"] = len(pool)
    debug["correction_target_lookup_count"] = len(additions)
    debug["correction_target_resolved_count"] = sum(item["status"] == "resolved" for item in resolutions)
    result["debug"] = debug
    return result


def _resolve_target_from_graph(graph_config, target_id, source_ids, edge_labels):
    with GraphClient(graph_config) as client:
        rows = (
            client.g.V()
            .or_(*[__.has(name, target_id) for name in _IDENTITY_PROPERTIES])
            .valueMap(True)
            .toList()
        )
        vertices = [normalize_vertex(row) for row in rows]
        if not vertices:
            return {"status": "failed", "reason": "Exact target identity was not found in UniGraph."}
        if len(vertices) != 1:
            return {"status": "ambiguous", "reason": "Exact target identity matched multiple UniGraph vertices."}
        vertex = vertices[0]
        target_vertex_id = vertex_id(vertex)

        def expand(frontier):
            rows = (
                client.g.V(*frontier)
                .as_("origin")
                .both(*edge_labels)
                .as_("neighbor")
                .select("origin", "neighbor")
                .by(T.id)
                .limit(TARGET_LOOKUP_MAX_EDGES + 1)
                .toList()
            )
            if len(rows) > TARGET_LOOKUP_MAX_EDGES:
                raise RuntimeError("Exact-target graph lookup exceeded its bounded edge limit.")
            return [(row["origin"], row["neighbor"]) for row in rows]

        try:
            nearest = _bfs_nearest_sources(target_vertex_id, source_ids, expand, TARGET_LOOKUP_MAX_DEPTH)
        except RuntimeError as exc:
            return {"status": "failed", "reason": str(exc)}
        if nearest is None:
            return {
                "status": "failed",
                "reason": f"Exact target was found in UniGraph but was not connected to an equipment boundary source within {TARGET_LOOKUP_MAX_DEPTH} hops.",
            }
        return {"status": "resolved", "vertex": _vertex_record(vertex), **nearest}


def _bfs_nearest_sources(target_id, source_ids, expand, max_depth):
    target_key = str(target_id)
    sources = {str(value) for value in source_ids}
    frontier = {target_id}
    visited = {target_key}
    parent = {target_key: None}
    for depth in range(1, max_depth + 1):
        next_frontier = {}
        for origin, neighbor in expand(frontier):
            origin_key, neighbor_key = str(origin), str(neighbor)
            if neighbor_key in visited:
                continue
            visited.add(neighbor_key)
            parent[neighbor_key] = origin_key
            next_frontier[neighbor_key] = neighbor
        found = sorted(set(next_frontier) & sources)
        if found:
            return {
                "depth": depth,
                "source_ids": found,
                "paths": {source: list(reversed(_parent_path(parent, source))) for source in found},
            }
        if not next_frontier:
            break
        frontier = set(next_frontier.values())
    return None


def _parent_path(parent, node):
    path = []
    while node is not None:
        path.append(node)
        node = parent.get(node)
    return path


def _boundary_sources(boundary_data):
    result = {}
    for boundary in boundary_data.get("equipment_boundaries") or []:
        equipment = boundary.get("equipment") or {}
        equipment_tag = _tag(equipment.get("properties") or {}) or str(equipment.get("id") or "")
        for item in boundary.get("component_boundaries") or []:
            component = item.get("component") or {}
            source_id = str(component.get("id") or "")
            if source_id:
                result[source_id] = {"equipment_tag": equipment_tag, "component": component}
    return result


def _pool_has_identity(pool, target_id):
    return any(target_id in {
        str(value).strip()
        for value in (item.get("candidate_id"), item.get("visual_node_id"), item.get("visual_id"), item.get("cnvrt_id"))
        if value not in (None, "")
    } for item in pool)


def _vertex_record(vertex):
    return {"id": vertex_id(vertex), "label": vertex_label(vertex), "properties": props_only(vertex)}


def _resolution(change_id, target_id, status, reason):
    return {"change_id": change_id, "target_id": target_id, "status": status, "reason": reason}


def _tag(properties):
    for key in ("tag_number", "tag", "Equipment Name", "name"):
        if properties.get(key) not in (None, "", []):
            return str(properties[key])
    return ""
