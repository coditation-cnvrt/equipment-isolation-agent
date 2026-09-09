"""Immutable Operations declarations. Declared values never prove field execution."""
from datetime import datetime, timedelta

from equipment_isolation.domain.safety_inputs import (
    FrozenJSON, boolean, context, enum, invalid, number, obj, string, strings, timestamp,
)

SECTIONS = ("equipment_state", "system_status", "valve_position_exceptions", "active_isolations", "active_overrides")
ROW_FIELDS = {
    "equipment_state": ("row_id", "tag", "state", "hilt_entity_id", "unigraph_vertex_id", "remarks"),
    "system_status": ("row_id", "system_or_header_tag", "service_code", "status", "pressure_barg", "temperature_c", "hilt_entity_id", "unigraph_vertex_id", "remarks"),
    "valve_position_exceptions": ("row_id", "tag", "actual_position", "reason", "hilt_entity_id", "unigraph_vertex_id"),
    "active_isolations": ("isolation_id", "scope", "boundary_points", "set_date", "expiry", "proving_record"),
    "active_overrides": ("sif_or_loop_tag", "override_type", "since", "reason", "authorisation_reference"),
}


def _dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class PlantStateDeclaration(FrozenJSON):
    @staticmethod
    def _validate(value):
        obj(value, ["schema_version", "revision_label", "context", "synthetic", "header", "section_coverage", *SECTIONS, "source_provenance"], "psd")
        enum(value["schema_version"], {"psd-v1"}, "schema_version")
        value["revision_label"] = string(value["revision_label"], "revision_label")
        value["context"] = context(value["context"])
        boolean(value["synthetic"], "synthetic")
        header = obj(value["header"], ["site", "unit", "declared_by", "role", "declared_at", "valid_until", "plant_mode"], "header")
        for key in ("site", "unit", "declared_by", "role"):
            header[key] = string(header[key], key)
        for key in ("declared_at", "valid_until"):
            header[key] = timestamp(header[key], key)
        if _dt(header["valid_until"]) <= _dt(header["declared_at"]):
            invalid("valid_until", "must follow declaration time")
        enum(header["plant_mode"], {"normal", "reduced_rate", "shutdown", "turnaround", "start_up"}, "plant_mode")
        obj(value["section_coverage"], SECTIONS, "section_coverage")
        if type(value["source_provenance"]) is not dict:
            invalid("source_provenance", "expected object")
        for section in SECTIONS:
            enum(value["section_coverage"][section], {"not_reviewed", "partial", "declared_complete"}, section)
            rows = value[section]
            if type(rows) is not list:
                invalid(section, "expected rows")
            seen_ids, seen_assets, seen_graph_ids = set(), set(), set()
            for row in rows:
                obj(row, ROW_FIELDS[section], section)
                key = ROW_FIELDS[section][0]
                row[key] = string(row[key], key)
                if row[key] in seen_ids:
                    invalid(section, "duplicate row identity")
                seen_ids.add(row[key])
                if section in {"equipment_state", "system_status", "valve_position_exceptions"}:
                    tag_key = "system_or_header_tag" if section == "system_status" else "tag"
                    row[tag_key] = string(row[tag_key], tag_key)
                    asset = row[tag_key]
                    if asset in seen_assets:
                        invalid(section, "conflicting duplicate asset declaration")
                    seen_assets.add(asset)
                    for identity in ("hilt_entity_id", "unigraph_vertex_id"):
                        if row[identity] is not None:
                            row[identity] = string(row[identity], identity)
                            qualified = (identity, row[identity])
                            if qualified in seen_graph_ids:
                                invalid(section, "duplicate graph identity declaration")
                            seen_graph_ids.add(qualified)
                    if section == "equipment_state":
                        enum(row["state"], {"running", "standby", "stopped", "isolated", "out_of_service"}, "state")
                    elif section == "system_status":
                        enum(row["status"], {"live", "depressurised", "out_of_service"}, "status")
                        row["service_code"] = string(row["service_code"], "service_code")
                        # Gauge pressure can be negative. Do not invent a pressure floor.
                        if row["pressure_barg"] is not None:
                            number(row["pressure_barg"], "pressure_barg")
                        if row["temperature_c"] is not None:
                            number(row["temperature_c"], "temperature_c", minimum=-273.15)
                    else:
                        row["actual_position"] = string(row["actual_position"], "actual_position")
                        row["reason"] = string(row["reason"], "reason")
                    if "remarks" in row and type(row["remarks"]) is not str:
                        invalid("remarks", "expected string")
                elif section == "active_isolations":
                    for field in ("scope", "boundary_points"):
                        row[field] = strings(row[field], field, nonempty=True)
                    for field in ("set_date", "expiry"):
                        row[field] = timestamp(row[field], field)
                    if _dt(row["expiry"]) <= _dt(row["set_date"]):
                        invalid("expiry", "must follow set_date")
                    if row["proving_record"] is not None:
                        row["proving_record"] = string(row["proving_record"], "proving_record")
                else:
                    for field in ("override_type", "reason"):
                        row[field] = string(row[field], field)
                    row["since"] = timestamp(row["since"], "since")
                    if row["authorisation_reference"] is not None:
                        row["authorisation_reference"] = string(row["authorisation_reference"], "authorisation_reference")
            value[section] = sorted(rows, key=lambda row: row[ROW_FIELDS[section][0]])
        return value

    def assess(self, *, plan_time: datetime, validity_hours: float) -> FrozenJSON:
        from equipment_isolation.domain.controlled_inputs import utc_timestamp
        number(validity_hours, "validity_hours", minimum=0)
        if validity_hours == 0:
            invalid("validity_hours", "must be positive")
        now = _dt(utc_timestamp(plan_time))
        data = self.to_dict()
        header = data["header"]
        start, declared_expiry = _dt(header["declared_at"]), _dt(header["valid_until"])
        try:
            expiry = min(declared_expiry, start + timedelta(hours=validity_hours))
        except OverflowError:
            invalid("validity_hours", "timestamp range exceeded")
        status = "not_yet_valid" if now < start else "expired" if now >= expiry else "within_declared_interval"
        gaps = {"psd_operations_authority_not_integrated", "psd_field_confirmation_required"}
        if data["synthetic"] or data["revision_label"].upper().startswith("MOCK-"):
            gaps.add("synthetic_input")
        if status != "within_declared_interval":
            gaps.add(f"psd_{status}")
        for section in SECTIONS:
            if data["section_coverage"][section] != "declared_complete":
                gaps.add(f"psd_inventory_incomplete:{section}")
            for row in data[section]:
                identity = row[ROW_FIELDS[section][0]]
                if section in {"equipment_state", "system_status", "valve_position_exceptions"}:
                    # IDs are declarations until reconciled against the pinned graph.
                    gaps.add(f"psd_identity_unreconciled:{section}:{identity}")
                if section == "system_status":
                    for field in ("pressure_barg", "temperature_c"):
                        if row[field] is None:
                            gaps.add(f"psd_missing:{identity}:{field}")
                    if row["status"] == "depressurised" and row["pressure_barg"] not in (None, 0):
                        gaps.add(f"psd_state_pressure_conflict:{identity}")
                elif section == "active_isolations":
                    gaps.add(f"psd_active_isolation_unverified:{identity}")
                    if now >= _dt(row["expiry"]):
                        gaps.add(f"psd_active_isolation_expired:{identity}")
                    if _dt(row["set_date"]) > start:
                        gaps.add(f"psd_future_isolation_at_declaration:{identity}")
                elif section == "active_overrides":
                    gaps.add(f"psd_override_authority_unverified:{identity}")
                    if _dt(row["since"]) > start:
                        gaps.add(f"psd_future_override_at_declaration:{identity}")
        return FrozenJSON.from_dict({"psd_hash": self.content_hash, "plan_time": utc_timestamp(plan_time),
            "effective_valid_until": utc_timestamp(expiry), "validity": status, "blockers": sorted(gaps),
            "declared_by": header["declared_by"], "isolation_proven": False, "safe_destination_proven": False})
