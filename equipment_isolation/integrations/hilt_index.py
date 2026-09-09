"""Indexing and summarization of the parsed HILT piping graph.

Builds id->node lookups, dedupes connected line records, and projects HILT nodes
and lines into the compact summaries that reach the output payload.

NOTE: ``_attr_value`` and ``_hilt_text_value`` here return ``None`` on a miss.
relief.py and instrument_context.py have same-shaped helpers returning ``""``.
tests/test_geometry_helpers.py pins that difference -- they are not interchangeable.
"""
from __future__ import annotations

from equipment_isolation.domain.topology import normalize_tag

# Alias, not a wrapper: normalize_tag is the single implementation.
_norm = normalize_tag


def _extract_hilt_source_context(payload):
    graph = (payload or {}).get("hilt_graph") if isinstance(payload, dict) else None
    if not isinstance(graph, dict):
        return {"lines_by_endpoint": {}, "nodes_by_id": {}, "node_count": 0, "link_count": 0, "source_line_context_count": 0}

    nodes = graph.get("nodes") or []
    links = graph.get("links") or []
    nodes_by_id = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id") or (node.get("payload") or {}).get("id") or (node.get("payload") or {}).get("source_id")
        if node_id:
            nodes_by_id[_norm(node_id)] = _hilt_node_summary(node)

    lines_by_endpoint = {}
    for link in links:
        if not isinstance(link, dict):
            continue
        payload = link.get("payload") or {}
        source = link.get("source") or payload.get("from")
        target = link.get("target") or payload.get("to")
        line = _hilt_line_summary(link, nodes_by_id)
        for endpoint in (source, target):
            if endpoint:
                lines_by_endpoint.setdefault(_norm(endpoint), []).append(line)

    return {
        "lines_by_endpoint": lines_by_endpoint,
        "nodes_by_id": nodes_by_id,
        "node_count": len(nodes),
        "link_count": len(links),
        "source_line_context_count": sum(len(items) for items in lines_by_endpoint.values()),
    }


def _hilt_node_summary(node):
    payload = node.get("payload") or {}
    bbox_location = payload.get("bounding_box_location") or {}
    return {
        "uuid": node.get("id") or payload.get("id") or payload.get("source_id"),
        "entity_type": payload.get("entity_type"),
        "entity_class": payload.get("entity_class"),
        "tag_number": _hilt_text_value(payload.get("text")) or _attr_value(payload.get("attributes"), "tag"),
        "bbox": _hilt_bbox(payload),
        "center": [bbox_location.get("x"), bbox_location.get("y")] if bbox_location else [],
    }


def _hilt_line_summary(link, nodes_by_id):
    payload = link.get("payload") or {}
    source = link.get("source") or payload.get("from")
    target = link.get("target") or payload.get("to")
    return {
        **_hilt_path_link_summary(link),
        "tag_number": _attr_value((payload.get("piping_network_segment") or {}).get("attributes"), "tag")
        or _attr_value(payload.get("attributes"), "tag"),
        "text": _hilt_text_value(payload.get("text")),
        "graphical_lines": _hilt_graphical_lines(payload.get("graphical_lines")),
        "connected_nodes": [nodes_by_id.get(_norm(value)) for value in (source, target) if nodes_by_id.get(_norm(value))],
    }


def _hilt_path_link_summary(link):
    """Project one HILT edge into ordered path facts without inferring service."""
    payload = link.get("payload") or {}
    source = link.get("source") or payload.get("from")
    target = link.get("target") or payload.get("to")
    segment = payload.get("piping_network_segment") or {}
    system = payload.get("piping_network_system") or {}
    segment_attributes = segment.get("attributes") or []
    system_attributes = system.get("attributes") or []
    payload_attributes = payload.get("attributes") or []
    segment_nominal_diameter = _attr_value(segment_attributes, "Nominal Diameter")
    system_nominal_diameter = _attr_value(system_attributes, "Nominal Diameter")
    segment_line_number = _attr_value(segment_attributes, "tag")
    system_line_number = _attr_value(system_attributes, "LineNumberAssignmentClass")
    design_pressure_values = _sourced_attribute_values(
        segment_attributes,
        system_attributes,
        payload_attributes,
        names=("Design Pressure", "DesignPressure"),
    )
    operating_pressure_values = _sourced_attribute_values(
        segment_attributes,
        system_attributes,
        payload_attributes,
        names=("Operating Pressure", "OperatingPressure"),
    )
    design_temperature_values = _sourced_attribute_values(
        segment_attributes,
        system_attributes,
        payload_attributes,
        names=("Design Temperature", "DesignTemperature"),
    )
    operating_temperature_values = _sourced_attribute_values(
        segment_attributes,
        system_attributes,
        payload_attributes,
        names=("Operating Temperature", "OperatingTemperature"),
    )
    service_evidence = []
    for source_kind, source_data, attributes in (
        ("segment", segment, segment_attributes),
        ("system", system, system_attributes),
        ("payload", payload, payload_attributes),
        ("link", link, []),
    ):
        values = list(source_data.items()) + [
            (attr.get("name"), attr.get("value"))
            for attr in attributes if isinstance(attr, dict)
        ]
        for name, value in values:
            key = "".join(ch for ch in str(name).casefold() if ch.isalnum())
            if key not in {"fluidcode", "servicecode"}:
                continue
            for code in value if isinstance(value, list) else [value]:
                if code not in (None, ""):
                    service_evidence.append({"source_kind": source_kind, "field": str(name), "service_code": code})
    service_evidence.sort(key=lambda row: (row["source_kind"], row["field"], str(row["service_code"])))
    return {
        "line_id": link.get("id") or payload.get("id") or payload.get("source_id"),
        "source": source,
        "target": target,
        "entity_type": payload.get("entity_type"),
        "entity_class": payload.get("entity_class"),
        "segment_id": segment.get("id") or payload.get("piping_network_segment_id"),
        "system_id": system.get("id") or payload.get("piping_network_system_id"),
        "line_number": _consistent_value(segment_line_number, system_line_number),
        "segment_line_number": segment_line_number,
        "system_line_number": system_line_number,
        "nominal_diameter": _consistent_value(segment_nominal_diameter, system_nominal_diameter),
        "segment_nominal_diameter": segment_nominal_diameter,
        "system_nominal_diameter": system_nominal_diameter,
        "fluid_code": _consistent_value(*(row["service_code"] for row in service_evidence)),
        "service_code_evidence": service_evidence,
        "service_designation": _attr_value(system_attributes, "ServiceDesignation"),
        "line_specification": _attr_value(segment_attributes, "Line Specification"),
        "insulation_code": _attr_value(segment_attributes, "Insulation Code"),
        "plant_area": _attr_value(segment_attributes, "Plant Area"),
        "design_pressure": _consistent_value(*design_pressure_values),
        "segment_design_pressure": design_pressure_values[0],
        "system_design_pressure": design_pressure_values[1],
        "payload_design_pressure": design_pressure_values[2],
        "operating_pressure": _consistent_value(*operating_pressure_values),
        "segment_operating_pressure": operating_pressure_values[0],
        "system_operating_pressure": operating_pressure_values[1],
        "payload_operating_pressure": operating_pressure_values[2],
        "design_temperature": _consistent_value(*design_temperature_values),
        "segment_design_temperature": design_temperature_values[0],
        "system_design_temperature": design_temperature_values[1],
        "payload_design_temperature": design_temperature_values[2],
        "operating_temperature": _consistent_value(*operating_temperature_values),
        "segment_operating_temperature": operating_temperature_values[0],
        "system_operating_temperature": operating_temperature_values[1],
        "payload_operating_temperature": operating_temperature_values[2],
        "flow": payload.get("flow"),
    }


def _dedupe_hilt_lines(lines):
    merged = {}
    for line in lines or []:
        if not isinstance(line, dict):
            continue
        key = line.get("line_id") or (line.get("source"), line.get("target"), line.get("entity_class"))
        if key and key not in merged:
            merged[key] = line
    return list(merged.values())


def _attr_value(attributes, name):
    target = str(name or "").strip().lower()
    for attr in attributes or []:
        if not isinstance(attr, dict):
            continue
        if str(attr.get("name") or "").strip().lower() == target:
            value = attr.get("value")
            if value not in (None, "", []):
                return str(value)
    return None


def _sourced_attribute_values(segment_attributes, system_attributes, payload_attributes, *, names):
    values = []
    for attributes in (segment_attributes, system_attributes, payload_attributes):
        found = None
        for name in names:
            value = _attr_value(attributes, name)
            if value not in (None, ""):
                found = value
                break
        values.append(found)
    return tuple(values)


def _consistent_value(*values):
    present = [str(value) for value in values if value not in (None, "")]
    if not present:
        return None
    normalized = {" ".join(value.casefold().split()) for value in present}
    return present[0] if len(normalized) == 1 else None


def _hilt_text_value(items):
    values = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if value not in (None, "", []):
            values.append(str(value))
    return ", ".join(values) if values else None


def _hilt_graphical_lines(lines):
    result = []
    for line in lines or []:
        if not isinstance(line, dict):
            continue
        p1 = line.get("p1") or {}
        p2 = line.get("p2") or {}
        if p1.get("x") is None or p1.get("y") is None or p2.get("x") is None or p2.get("y") is None:
            continue
        result.append(
            {
                "point1": [round(float(p1.get("x")), 4), round(float(p1.get("y")), 4)],
                "point2": [round(float(p2.get("x")), 4), round(float(p2.get("y")), 4)],
                "line_type": line.get("line_type"),
            }
        )
    return result


def _hilt_nodes_by_id(hilt_payload, y_flip):
    graph = (hilt_payload or {}).get("hilt_graph") if isinstance(hilt_payload, dict) else None
    if not isinstance(graph, dict):
        return {}
    nodes = {}
    for node in graph.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        payload = node.get("payload") or {}
        node_id = node.get("id") or payload.get("id") or payload.get("source_id")
        if not node_id:
            continue
        summary = {
            "uuid": str(node_id),
            "source_id": payload.get("source_id"),
            "entity_type": payload.get("entity_type"),
            "entity_class": payload.get("entity_class"),
            "tag_number": _hilt_text_value(payload.get("text")) or _attr_value(payload.get("attributes"), "tag"),
            "bbox": _hilt_bbox(payload, y_flip=y_flip),
        }
        for key in (node_id, payload.get("id"), payload.get("source_id"), payload.get("uuid")):
            if key:
                nodes[_norm(key)] = summary
    return nodes


def _find_hilt_node(hilt_node_by_id, *values):
    for value in values:
        if value in (None, "", []):
            continue
        node = hilt_node_by_id.get(_norm(value))
        if node:
            return node
    return None


def _find_hilt_node_by_tag(hilt_node_by_id, tag):
    normalized = _norm(tag)
    if not normalized:
        return None
    for node in hilt_node_by_id.values():
        if _norm(node.get("tag_number")) == normalized:
            return node
    return None


def _hilt_bbox(payload, y_flip=None):
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
    y = (float(y_flip) - cy - h / 2.0) if y_flip is not None else (cy - h / 2.0)
    return [int(round(x)), int(round(y)), int(round(w)), int(round(h))]
