from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest

from equipment_isolation.domain.controlled_inputs import ControlledInputError, prepare_content, validate_approval
from equipment_isolation.domain.safety_inputs import FrozenJSON, SicDelta, SicProfile, StructuredWorkScope, compose_sic
from equipment_isolation.domain.plant_state import PlantStateDeclaration
from equipment_isolation.integrations.safety_input_adapters import sic_from_mock, psd_from_mock

DOCS = Path(__file__).parents[1] / "docs"


def fixture(kind):
    return json.loads((DOCS / f"mock_{kind}_pnid_2151.json").read_text())


def work_scope():
    return StructuredWorkScope.from_dict({"schema_version": "work-scope-v1", "activity_type": "inspect cooler",
        "expected_duration_days": 2, "shift_coverage": "multiple_shifts", "containment_break": True,
        "continuously_attended": False, "personnel_enter_boundary": False,
        "hot_work_on_or_within_boundary": False, "equipment_leaves_site": False})


def delta(base, changes, **extra):
    return SicDelta.from_dict({"schema_version": "sic-process-delta-v1", "revision_label": "MOCK-DELTA-1",
        "context": base.to_dict()["context"], "synthetic": True, "base_hash": base.content_hash,
        "base_revision_label": base.to_dict()["revision_label"], "changes": changes,
        "justification": "Development case", **extra})


class SafetyInputContractTests(unittest.TestCase):
    def test_work_scope_is_strict_and_has_no_legacy_boolean_default(self):
        valid = work_scope().to_dict()
        for changes in ({"containment_break": "false"}, {"expected_duration_days": True},
                        {"expected_duration_days": -1}, {"expected_duration_days": float("nan")},
                        {"shift_coverage": "overnight"}, {"high_risk_service": False}):
            with self.subTest(changes=changes), self.assertRaises(ControlledInputError):
                StructuredWorkScope.from_dict({**valid, **changes})
        valid.pop("continuously_attended")
        with self.assertRaises(ControlledInputError):
            StructuredWorkScope.from_dict(valid)

    def test_nested_data_cannot_change_after_capture(self):
        source = {"nested": [{"value": 1}]}
        frozen = FrozenJSON.from_dict(source)
        source["nested"][0]["value"] = 2
        projection = frozen.to_dict()
        projection["nested"][0]["value"] = 3
        self.assertEqual(frozen.to_dict(), {"nested": [{"value": 1}]})
        with self.assertRaises(FrozenInstanceError):
            frozen._canonical = b'{}'
        with self.assertRaises(ControlledInputError):
            StructuredWorkScope(b'{}')

    def test_mock_sic_normalizes_without_approval_or_defaults(self):
        source = fixture("sic")
        profile = sic_from_mock(source)
        self.assertEqual(profile.to_dict()["parameters"]["proving"]["acceptance_criterion"], None)
        self.assertIn("synthetic_input", profile.blockers)
        self.assertEqual(source, fixture("sic"))
        canonical, validation = prepare_content("sic", "sic-process-v1", profile.to_dict())
        self.assertEqual(validation["status"], "draft_validated")
        with self.assertRaises(ControlledInputError):
            validate_approval("sic", "sic-process-v1", canonical)

    def test_sic_rejects_units_unknown_fields_and_invalid_domains(self):
        valid = sic_from_mock(fixture("sic")).to_dict()
        mutations = [
            ("barrier_policy", "small_bore_threshold_dn", 0),
            ("barrier_policy", "actuated_valve_as_barrier", "yes"),
            ("barrier_policy", "soft_seat_permitted_for_hot_work", 0),
            ("proving", "pressure_decay_hold_minutes", -1),
            ("plant_state", "validity_hours", 0),
            ("barrier_policy", "small_bore_threshold_inches", 2),
        ]
        for group, key, value in mutations:
            candidate = deepcopy(valid)
            candidate["parameters"][group][key] = value
            with self.subTest(key=key), self.assertRaises(ControlledInputError):
                SicProfile.from_dict(candidate)
        candidate = deepcopy(valid)
        candidate["parameters"]["gas_testing"]["acceptance_criteria"].update(oxygen_percent_min=25, oxygen_percent_max=20)
        with self.assertRaises(ControlledInputError):
            SicProfile.from_dict(candidate)

    def test_sic_delta_requires_exact_base_and_scope(self):
        base = sic_from_mock(fixture("sic"))
        path = "/parameters/escalation_thresholds/duration_escalate_days"
        effective, trace = compose_sic(base, delta(base, {path: 5}))
        self.assertEqual(effective.to_dict()["parameters"]["escalation_thresholds"]["duration_escalate_days"], 5)
        self.assertEqual(base.to_dict()["parameters"]["escalation_thresholds"]["duration_escalate_days"], 7)
        self.assertEqual(trace.to_dict()["parameter_origins"][path], delta(base, {path: 5}).content_hash)
        for extra in ({"base_hash": "0"*64}, {"base_revision_label": "wrong"},
                      {"context": {"cnvrt_project_id": "277", "collection_id": "different"}}):
            with self.subTest(extra=extra), self.assertRaises(ControlledInputError):
                compose_sic(base, delta(base, {path: 5}, **extra))

    def test_delta_cannot_modify_identity_approval_or_floors_and_revalidates_values(self):
        base = sic_from_mock(fixture("sic"))
        for path in ("/context", "/synthetic", "/approved_by", "/non_overridable_floors", "/parameters/barrier_policy"):
            with self.subTest(path=path), self.assertRaises(ControlledInputError):
                delta(base, {path: {}})
        with self.assertRaises(ControlledInputError):
            compose_sic(base, delta(base, {"/parameters/plant_state/validity_hours": 0}))
        self.assertIn("synthetic_input", compose_sic(base, delta(base, {"/parameters/plant_state/validity_hours": 12}, synthetic=False))[0].blockers)

    def test_matrix_override_requires_justification_and_approver_reference(self):
        profile = sic_from_mock(fixture("sic")).to_dict()
        row = {"hsc": 2, "ec": "B", "configuration": {"barrier_count": 2, "bleed_required": True,
            "positive_barrier_count": 1, "physical_disconnection_required": False, "both_sides_blinded_required": False},
            "justification": "Draft example", "approver_reference": "unverified-imported-claim"}
        profile["matrix_overrides"] = [row]
        self.assertIn("sic_approval_not_integrated", SicProfile.from_dict(profile).blockers)
        for key in ("justification", "approver_reference"):
            candidate = deepcopy(profile)
            candidate["matrix_overrides"][0][key] = ""
            with self.assertRaises(ControlledInputError):
                SicProfile.from_dict(candidate)
        profile["matrix_overrides"].append(deepcopy(row))
        with self.assertRaises(ControlledInputError):
            SicProfile.from_dict(profile)

    def test_psd_expiry_uses_explicit_time_and_sic_maximum(self):
        psd = psd_from_mock(fixture("psd"))
        def assess(stamp, hours=24):
            return psd.assess(plan_time=datetime.fromisoformat(stamp), validity_hours=hours).to_dict()
        self.assertEqual(assess("2026-09-08T07:00:00+00:00")["validity"], "within_declared_interval")
        self.assertEqual(assess("2026-09-09T06:00:00+00:00")["validity"], "expired")
        self.assertEqual(assess("2026-09-08T08:00:00+00:00", 2)["validity"], "expired")
        self.assertEqual(assess("2026-09-08T05:00:00+00:00")["validity"], "not_yet_valid")
        with self.assertRaises(ControlledInputError):
            psd.assess(plan_time=datetime(2026, 9, 8), validity_hours=24)

    def test_psd_null_is_not_zero_and_empty_is_not_reviewed(self):
        psd = psd_from_mock(fixture("psd"))
        self.assertIsNone(next(row for row in psd.to_dict()["system_status"] if row["row_id"] == "SYS-VRP")["pressure_barg"])
        result = psd.assess(plan_time=datetime(2026,9,8,7,tzinfo=timezone.utc), validity_hours=24).to_dict()
        self.assertIn("psd_missing:SYS-VRP:pressure_barg", result["blockers"])
        self.assertIn("psd_inventory_incomplete:active_isolations", result["blockers"])
        self.assertFalse(result["isolation_proven"])
        self.assertFalse(result["safe_destination_proven"])

    def test_all_researched_psd_scenarios_remain_unverified(self):
        for scenario in fixture("psd")["test_scenarios"]:
            candidate = fixture("psd")
            candidate.update(scenario.get("replacements", {}))
            for override in scenario.get("row_overrides", []):
                row = next(row for row in candidate[override["section"]] if row["row_id"] == override["row_id"])
                row.update(override["changes"])
            psd = psd_from_mock(candidate)
            stamp = scenario.get("evaluation_time", "2026-09-08T07:00:00Z")
            result = psd.assess(plan_time=datetime.fromisoformat(stamp.replace("Z", "+00:00")), validity_hours=24).to_dict()
            with self.subTest(scenario=scenario["scenario_id"]):
                self.assertIn("synthetic_input", result["blockers"])
                self.assertFalse(result["isolation_proven"])
                self.assertFalse(result["safe_destination_proven"])
                if scenario["scenario_id"] == "expired_declaration":
                    self.assertEqual(result["validity"], "expired")
                if scenario["scenario_id"] == "existing_isolation_and_override":
                    self.assertTrue(psd.to_dict()["active_isolations"])
                    self.assertTrue(psd.to_dict()["active_overrides"])

    def test_psd_rejects_conflicts_unknown_fields_and_invalid_time(self):
        valid = psd_from_mock(fixture("psd")).to_dict()
        for mutate in (
            lambda p: p["equipment_state"].append(deepcopy(p["equipment_state"][0])),
            lambda p: p["system_status"][0].update(pressure_barg="0"),
            lambda p: p["system_status"][0].update(temperature_c=-274),
            lambda p: p["system_status"][0].update(pressure_psi=20),
            lambda p: p["header"].update(valid_until=p["header"]["declared_at"]),
            lambda p: p["header"].update(declared_at="2026-09-08"),
        ):
            candidate=deepcopy(valid)
            mutate(candidate)
            with self.assertRaises(ControlledInputError):
                PlantStateDeclaration.from_dict(candidate)

    def test_row_permutations_are_canonical(self):
        value = psd_from_mock(fixture("psd")).to_dict()
        original = PlantStateDeclaration.from_dict(value).content_hash
        for section in ("system_status", "equipment_state"):
            value[section].reverse()
        self.assertEqual(PlantStateDeclaration.from_dict(value).content_hash, original)

    def test_mock_adapters_cannot_relabel_approved_content(self):
        for kind, adapter in (("sic", sic_from_mock), ("psd", psd_from_mock)):
            value = fixture(kind)
            value["document"]["status"] = "approved"
            with self.assertRaises(ControlledInputError):
                adapter(value)
