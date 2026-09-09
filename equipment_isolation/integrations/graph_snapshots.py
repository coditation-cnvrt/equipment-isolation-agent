"""Capture already-fetched exports without asserting provider snapshot guarantees.

No network calls are made here. The current HILT/job and live Gremlin interfaces
cannot establish atomic, complete execution inputs; those gaps remain explicit.
"""
from copy import deepcopy
from datetime import datetime

from equipment_isolation.domain.controlled_inputs import utc_timestamp
from equipment_isolation.domain.safety_inputs import FrozenJSON, context, enum, invalid, obj, string, timestamp


from equipment_isolation.domain.source_snapshots import GraphSnapshot, _identity, _consistent


def capture_hilt_export(payload, *, planning_context, captured_at: datetime, source_revision=None):
    if type(payload) is not dict:
        invalid("hilt", "expected exported graph object")
    wrappers = [key for key in ("hilt_graph", "graph") if key in payload]
    if len(wrappers) > 1:
        invalid("hilt", "ambiguous graph wrappers")
    graph = payload[wrappers[0]] if wrappers else payload
    if type(graph) is not dict or type(graph.get("nodes")) is not list or type(graph.get("links")) is not list:
        invalid("hilt", "expected exported nodes and links")
    nodes, edges = [], []
    for row in graph["nodes"]:
        if type(row) is not dict or type(row.get("payload", {})) is not dict:
            invalid("node", "malformed source record")
        # Outer graph ID is topology identity; payload IDs may be domain IDs.
        ident = row.get("id") if row.get("id") is not None else row.get("payload", {}).get("id")
        nodes.append({"id": _identity(ident, "node.id"), "record": deepcopy(row)})
    for row in graph["links"]:
        if type(row) is not dict or type(row.get("payload", {})) is not dict:
            invalid("link", "malformed source record")
        facts = row.get("payload", {})
        ident = row.get("id") if row.get("id") is not None else facts.get("id")
        edges.append({"id": _identity(ident, "link.id"),
            "source": _consistent([row.get("source"), facts.get("from")], "link.source"),
            "target": _consistent([row.get("target"), facts.get("to")], "link.target"), "record": deepcopy(row)})
    return GraphSnapshot.from_dict({"schema_version": "captured-graph-v1", "source": "hilt",
        "context": planning_context, "captured_at": utc_timestamp(captured_at), "source_revision": source_revision,
        "graph": {"nodes": nodes, "edges": edges, "metadata": {key: deepcopy(value) for key, value in graph.items() if key not in {"nodes", "links"}}}})


def capture_unigraph_export(payload, *, planning_context, captured_at: datetime, source_revision=None):
    """Accept normalized JSON node/edge exports, never live traversal callbacks.

    Nodes use id/label or T.id/T.label; edges use id/source/target/label or the
    preserved edge_id/from_node_id/to_node_id/edge_label representation.
    """
    obj(payload, ["nodes", "edges"], "unigraph", ["metadata"])
    if type(payload["nodes"]) is not list or type(payload["edges"]) is not list:
        invalid("unigraph", "expected node/edge arrays")
    nodes, edges = [], []
    for row in payload["nodes"]:
        if type(row) is not dict:
            invalid("node", "expected normalized JSON object")
        ident = _consistent([row.get("id"), row.get("T.id")], "node.id")
        _consistent([row.get("label"), row.get("T.label")], "node.label")
        nodes.append({"id": ident, "record": deepcopy(row)})
    for row in payload["edges"]:
        if type(row) is not dict:
            invalid("edge", "expected normalized JSON object")
        _consistent([row.get("label"), row.get("edge_label")], "edge.label")
        edges.append({"id": _consistent([row.get("id"), row.get("edge_id")], "edge.id"),
            "source": _consistent([row.get("source"), row.get("from_node_id")], "edge.source"),
            "target": _consistent([row.get("target"), row.get("to_node_id")], "edge.target"), "record": deepcopy(row)})
    return GraphSnapshot.from_dict({"schema_version": "captured-graph-v1", "source": "unigraph",
        "context": planning_context, "captured_at": utc_timestamp(captured_at), "source_revision": source_revision,
        "graph": {"nodes": nodes, "edges": edges, "metadata": payload.get("metadata", {})}})
