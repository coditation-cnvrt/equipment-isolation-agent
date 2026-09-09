"""Lossless ordered path facts shared by candidate and plan projections."""
from copy import deepcopy

PATH_FIELDS = (
    "path_node_ids", "path_node_classes", "path_link_ids", "path_link_facts",
    "path_edge_ids", "path_edge_labels", "path_edge_facts", "path_node_facts",
)


def path_facts(source: dict) -> dict:
    result = {}
    for field in PATH_FIELDS:
        aliases = (field, f"branch_{field}", f"graph_{field}")
        if field == "path_node_ids":
            aliases += ("graph_path_ids",)
        if field == "path_link_ids":
            aliases += ("link_ids",)
        result[field] = deepcopy(next((source[key] for key in aliases if source.get(key)), []))
    return result
