"""Explicit development-fixture adapters. Never infer approval or graph identity."""
from copy import deepcopy

from equipment_isolation.domain.plant_state import PlantStateDeclaration, ROW_FIELDS, SECTIONS
from equipment_isolation.domain.safety_inputs import SicProfile, SIC_FIELDS, enum, invalid, obj


def _fixture(value, kind):
    if type(value) is not dict:
        invalid("fixture", "expected object")
    enum(value.get("schema_version"), {f"mock-{kind}-v0.1"}, "fixture.schema_version")
    obj(value.get("document"), ["title", "revision", "status", "approved_by", "approved_date",
        "cnvrt_project_id", "collection_id", "unigraph_project_id", "pnid_job_id", "warning"], "fixture.document")
    if type(value.get("metadata")) is not dict:
        invalid("fixture.metadata", "expected object")
    if value.get("metadata", {}).get("synthetic") is not True or value.get("document", {}).get("status") != "draft_mock_unapproved":
        invalid("fixture", "mock adapter accepts only explicit unapproved synthetic inputs")
    return deepcopy(value)


def _context(document, drawing=True):
    keys = ["cnvrt_project_id", "collection_id"] + (["unigraph_project_id"] if drawing else [])
    result = {key: document[key] for key in keys}
    if drawing:
        result["job_id"] = document["pnid_job_id"]
    return result


def sic_from_mock(value) -> SicProfile:
    data = _fixture(value, "sic")
    # This adapter covers this versioned fixture format, not arbitrary SIC YAML.
    obj(data, ["schema_version", "document", "metadata", *SIC_FIELDS, "matrix", "permits",
               "unresolved_decisions", "research_sources", "parameter_provenance"], "mock_sic")
    if data["permits"]["enabled_permit_types"] or data["permits"]["templates"] or data["permits"]["signature_blocks"]:
        invalid("permits", "fixture adapter does not support permit configuration")
    params = {}
    extra = {
        "proving": {"status"}, "plant_state": {"on_expiry"},
        "gas_testing": {"required_analytes_for_mock_review", "acceptance_criteria", "status"},
        "purging": {"status"}, "tagging": {"operational_template"},
        "electrical": {"separate_authorised_electrical_assessment_required"},
    }
    for group, validators in SIC_FIELDS.items():
        source = data[group]
        required = set(validators)
        if group == "gas_testing":
            required.remove("required_analytes")
        obj(source, required, group, extra.get(group, ()))
        params[group] = {key: source[key] for key in required}
    params["gas_testing"]["required_analytes"] = data["gas_testing"]["required_analytes_for_mock_review"]
    params["gas_testing"]["acceptance_criteria"] = data["gas_testing"]["acceptance_criteria"]
    if data["matrix"]["base_matrix_reference"] != "project_requirements_v1_section_6_3":
        invalid("matrix", "unsupported base matrix")
    return SicProfile.from_dict({"schema_version": "sic-process-v1", "revision_label": data["document"]["revision"],
        "context": _context(data["document"], drawing=False), "synthetic": True, "parameters": params,
        "matrix_overrides": data["matrix"]["overrides"], "unresolved_decisions": data["unresolved_decisions"],
        "source_provenance": {"fixture_schema": data["schema_version"], "document": data["document"],
            "research_sources": data["research_sources"], "parameter_provenance": data["parameter_provenance"],
            "unsupported_operational_groups": {"permits": data["permits"]},
            "fixture_annotations": {group: {key: val for key, val in data[group].items() if key not in params[group]} for group in SIC_FIELDS}}})


def psd_from_mock(value) -> PlantStateDeclaration:
    data = _fixture(value, "psd")
    obj(data, ["schema_version", "document", "metadata", "header", *SECTIONS, "section_coverage",
               "handover", "identity_bindings", "test_scenarios", "research_sources", "expected_base_outcome"], "mock_psd")
    if data["identity_bindings"]:
        invalid("identity_bindings", "mock identities must not be treated as reconciled")
    header_keys = ("site", "unit", "declared_by", "role", "declared_at", "valid_until", "plant_mode")
    obj(data["header"], header_keys, "header", ["declaration_verified", "validity_basis"])
    if data["header"].get("declaration_verified") is not False:
        invalid("declaration_verified", "mock adapter cannot attest verification")
    result = {"schema_version": "psd-v1", "revision_label": data["document"]["revision"],
        "context": _context(data["document"]), "synthetic": True,
        "header": {key: data["header"][key] for key in header_keys}, "section_coverage": {},
        "source_provenance": {"fixture_schema": data["schema_version"], "document": data["document"],
            "research_sources": data["research_sources"], "handover": data["handover"], "row_annotations": {}}}
    extras = {"equipment_state": {"description", "provenance"},
        "system_status": {"provenance", "usable_as_bleed_destination"},
        "valve_position_exceptions": set(), "active_isolations": {"verification_status"}, "active_overrides": set()}
    for section in SECTIONS:
        coverage = enum(data["section_coverage"][section], {"partial_mock_inventory", "not_reviewed", "declared_complete"}, section)
        result["section_coverage"][section] = "partial" if coverage == "partial_mock_inventory" else coverage
        result[section] = []
        result["source_provenance"]["row_annotations"][section] = {}
        for row in data[section]:
            obj(row, ROW_FIELDS[section], section, extras[section])
            result[section].append({key: row[key] for key in ROW_FIELDS[section]})
            result["source_provenance"]["row_annotations"][section][str(row[ROW_FIELDS[section][0]])] = {
                key: val for key, val in row.items() if key not in ROW_FIELDS[section]
            }
    return PlantStateDeclaration.from_dict(result)
