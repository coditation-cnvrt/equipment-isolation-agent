"""Immutable graph capture contract, without network or provider dependencies."""
from equipment_isolation.domain.safety_inputs import FrozenJSON, context, enum, invalid, obj, string, timestamp


class GraphSnapshot(FrozenJSON):
    @staticmethod
    def _validate(value):
        obj(value, ["schema_version", "source", "context", "captured_at", "source_revision", "graph"], "graph_snapshot")
        enum(value["schema_version"], {"captured-graph-v1"}, "schema_version")
        enum(value["source"], {"hilt", "unigraph"}, "source")
        value["context"] = context(value["context"])
        value["captured_at"] = timestamp(value["captured_at"], "captured_at")
        if value["source_revision"] is not None:
            value["source_revision"] = string(value["source_revision"], "source_revision")
        graph = obj(value["graph"], ["nodes", "edges", "metadata"], "graph")
        if type(graph["metadata"]) is not dict:
            invalid("graph.metadata", "expected object")
        for collection in ("nodes", "edges"):
            if type(graph[collection]) is not list:
                invalid(collection, "expected array")
            seen = set()
            for row in graph[collection]:
                keys = ["id", "record"] + (["source", "target"] if collection == "edges" else [])
                obj(row, keys, collection)
                row["id"] = string(row["id"], "id")
                if row["id"] in seen:
                    invalid(collection, "duplicate source identity")
                seen.add(row["id"])
                if type(row["record"]) is not dict:
                    invalid("record", "expected original source record")
                record = row["record"]
                if value["source"] == "hilt":
                    facts = record.get("payload", {})
                    if type(facts) is not dict:
                        invalid("payload", "expected object")
                    original_id = record.get("id") if record.get("id") is not None else facts.get("id")
                    if _identity(original_id, "record.id") != row["id"]:
                        invalid("record.id", "normalized identity differs from captured record")
                    endpoints = [("source", [record.get("source"), facts.get("from")]),
                                 ("target", [record.get("target"), facts.get("to")])]
                else:
                    alias = "edge_id" if collection == "edges" else "T.id"
                    if _consistent([record.get("id"), record.get(alias)], "record.id") != row["id"]:
                        invalid("record.id", "normalized identity differs from captured record")
                    _consistent([record.get("label"), record.get("edge_label" if collection == "edges" else "T.label")], "record.label")
                    endpoints = [("source", [record.get("source"), record.get("from_node_id")]),
                                 ("target", [record.get("target"), record.get("to_node_id")])]
                if collection == "edges":
                    for key, aliases in endpoints:
                        if _consistent(aliases, key) != row[key]:
                            invalid(key, "normalized endpoint differs from captured record")
                for key in ("source", "target") if collection == "edges" else ():
                    row[key] = string(row[key], key)
            graph[collection].sort(key=lambda row: row["id"])
        return value

    @property
    def graph_hash(self):
        # Capture clock/provenance is audit metadata, not topology semantics.
        data = self.to_dict()
        return FrozenJSON.from_dict({"source": data["source"], "context": data["context"], "graph": data["graph"]}).content_hash

    @property
    def blockers(self):
        data = self.to_dict()
        gaps = {f"{data['source']}_coverage_unverified", f"{data['source']}_provider_consistency_unverified"}
        ids = {node["id"] for node in data["graph"]["nodes"]}
        if not ids:
            gaps.add(f"{data['source']}_empty_graph")
        for edge in data["graph"]["edges"]:
            for endpoint in ("source", "target"):
                if edge[endpoint] not in ids:
                    gaps.add(f"{data['source']}_unresolved_endpoint:{edge['id']}:{endpoint}")
        return tuple(sorted(gaps))


def _identity(value, path):
    if type(value) not in (int, str):
        invalid(path, "missing explicit graph identity")
    return string(str(value), path)


def _consistent(values, path):
    values = [_identity(item, path) for item in values if item is not None]
    if not values or len(set(values)) != 1:
        invalid(path, "missing or conflicting identity aliases")
    return values[0]
