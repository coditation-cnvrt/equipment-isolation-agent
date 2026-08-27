import unittest

from config import RunConfig
from loto import build_loto_procedure


def candidate(candidate_id, entity_class, source="N1", tag=None):
    return {
        "equipment_tag": "P3",
        "candidate_id": candidate_id,
        "candidate_label": entity_class,
        "visual_node_id": f"drawing-{candidate_id}",
        "tag_number": tag,
        "properties": {"entity_class": entity_class},
        "source_component_tag": source,
        "source_flow_role": "inlet",
        "traversal_depth": 1,
        "bbox": [10, 10, 20, 20],
    }


class LotoActionTests(unittest.TestCase):
    def test_flange_is_positive_hold_not_close_lock_valve(self):
        procedure = build_loto_procedure(
            {
                "assurance_status": "provisional_unproven_isolation",
                "candidates": [candidate("flange-1", "flange", source="P2A")],
                "isolation_validation": {},
            },
            RunConfig(equipment_tag="P3"),
        )

        actions = [step["action"] for step in procedure["ordered_steps"]]
        self.assertTrue(any("Field-verify flange/line-break point" in action for action in actions))
        self.assertTrue(any("approved blind/spade" in action for action in actions))
        self.assertFalse(any("Close & lock flange" in action for action in actions))
        device = procedure["phases"][2]["field_confirmed_positive_devices"][0]
        self.assertEqual(device["operation_kind"], "field_confirmed_positive_isolation")
        self.assertTrue(device["positive_isolation_requires_field_confirmation"])

    def test_check_valve_does_not_close_and_lock(self):
        procedure = build_loto_procedure(
            {
                "assurance_status": "not_isolated",
                "candidates": [candidate("check-1", "check_valve", source="N1", tag="CHK-1")],
                "isolation_validation": {},
            },
            RunConfig(equipment_tag="P3"),
        )

        actions = [step["action"] for step in procedure["ordered_steps"]]
        self.assertTrue(any("no isolation devices identified" in action for action in actions))
        self.assertFalse(any("Close & lock CHK-1" in action for action in actions))

    def test_valve_operation_and_lock_tag_are_separate_phases(self):
        procedure = build_loto_procedure(
            {
                "assurance_status": "provisional_unproven_isolation",
                "candidates": [candidate("valve-1", "gate_valve", source="N1", tag="XV-1")],
                "isolation_validation": {},
            },
            RunConfig(equipment_tag="P3"),
        )

        phase_3 = [step["action"] for step in procedure["ordered_steps"] if step["phase"] == 3]
        phase_4 = [step["action"] for step in procedure["ordered_steps"] if step["phase"] == 4]
        self.assertTrue(any("Close XV-1" in action for action in phase_3))
        self.assertFalse(any("lock" in action.lower() for action in phase_3))
        self.assertTrue(any("Affix lock/tag to XV-1" in action for action in phase_4))

    def test_unavailable_valve_is_not_in_loto_actions(self):
        unavailable = candidate("valve-1", "gate_valve", source="N1", tag="XV-FAULTY")
        unavailable.update(availability_status="unavailable", available_for_isolation=False)
        procedure = build_loto_procedure(
            {"assurance_status": "not_isolated", "candidates": [unavailable], "isolation_validation": {}},
            RunConfig(equipment_tag="P3"),
        )

        actions = [step["action"] for step in procedure["ordered_steps"]]
        self.assertTrue(any("no isolation devices identified" in action for action in actions))
        self.assertFalse(any("XV-FAULTY" in action for action in actions))

    def test_unavailable_scheme_device_cannot_replace_authoritative_barrier(self):
        unavailable = candidate("faulty", "gate_valve", source="L3", tag="XV-FAULTY")
        unavailable.update(availability_status="unavailable", available_for_isolation=False)
        replacement = candidate("replacement", "gate_valve", source="L3", tag="XV-REPLACEMENT")
        procedure = build_loto_procedure(
            {
                "assurance_status": "provisional_unproven_isolation",
                "candidates": [unavailable, replacement],
                "isolation_validation": {
                    "barrier_candidate_ids": ["replacement"],
                    "isolation_obligations": {
                        "items": [{"branch_id": "L3", "status": "isolated", "selected_candidate_ids": ["replacement"]}]
                    },
                },
                "detected_isolation_schemes": {
                    "items": [{
                        "source_component": "L3",
                        "scheme_type": "double_block",
                        "devices": [{"id": "faulty", "tag": "XV-FAULTY", "entity_class": "gate_valve"}],
                    }]
                },
            },
            RunConfig(equipment_tag="P3"),
        )

        operational = [step for step in procedure["ordered_steps"] if step.get("importance") == "operational"]
        self.assertFalse(any(step.get("device_uuid") == "faulty" for step in operational))
        self.assertEqual(
            [step["phase"] for step in operational if step.get("device_uuid") == "replacement"],
            [3, 4],
        )
        self.assertEqual(procedure["integrity"]["status"], "valid")

    def test_steps_have_stable_identity_and_exact_drawing_target(self):
        procedure = build_loto_procedure(
            {
                "assurance_status": "provisional_unproven_isolation",
                "candidates": [candidate("valve-1", "gate_valve", tag="XV-1")],
                "isolation_validation": {"barrier_candidate_ids": ["valve-1"]},
            },
            RunConfig(equipment_tag="P3"),
        )

        step = next(item for item in procedure["ordered_steps"] if item.get("device_uuid") == "valve-1")
        self.assertEqual(step["target"]["drawing_entity_id"], "drawing-valve-1")
        self.assertEqual(step["step_id"], "phase:3:operate_isolation:valve-1")
        self.assertEqual(step["covered_branches"], [{"id": "N1", "label": "N1"}])
        self.assertTrue(step["locatable"])

    def test_field_hold_requirement_is_integrated_into_its_loto_phase(self):
        procedure = build_loto_procedure(
            {
                "assurance_status": "provisional_unproven_isolation",
                "candidates": [candidate("valve-1", "gate_valve", tag="XV-1")],
                "isolation_validation": {"barrier_candidate_ids": ["valve-1"]},
                "plan_readiness": {
                    "field_execution_hold_points": [{
                        "requirement_id": "hold-bypass",
                        "loto_phase": 3,
                        "instruction": "Confirm no open bypass exists around the selected barrier.",
                        "method_identified": False,
                        "evidence_targets": [{"entity_id": "bypass-1", "tag": "BP-1", "entity_class": "process_line"}],
                    }]
                },
            },
            RunConfig(equipment_tag="P3"),
        )

        hold = next(step for step in procedure["ordered_steps"] if step.get("requirement_id") == "hold-bypass")
        self.assertEqual(hold["phase"], 3)
        self.assertEqual(hold["importance"], "hold_point")
        self.assertTrue(hold["field_gap"])
        self.assertEqual(hold["target"]["drawing_entity_id"], "bypass-1")

    def test_validator_and_branch_selection_mismatch_blocks_procedure(self):
        procedure = build_loto_procedure(
            {
                "assurance_status": "provisional_unproven_isolation",
                "candidates": [candidate("validator-barrier", "gate_valve"), candidate("branch-only", "gate_valve")],
                "isolation_validation": {
                    "barrier_candidate_ids": ["validator-barrier"],
                    "isolation_obligations": {
                        "items": [{"branch_id": "L3", "status": "isolated", "selected_candidate_ids": ["branch-only"]}]
                    },
                },
            },
            RunConfig(equipment_tag="P3"),
        )

        self.assertEqual(procedure["integrity"]["status"], "blocked")
        self.assertTrue(any(
            issue.get("code") == "authoritative_barrier_missing" and issue.get("target_id") == "branch-only"
            for issue in procedure["integrity"]["issues"]
        ))

    def test_companion_line_context_adds_phase_one_review_step(self):
        procedure = build_loto_procedure(
            {
                "assurance_status": "provisional_unproven_isolation",
                "candidates": [candidate("valve-1", "gate_valve", source="N1")],
                "isolation_validation": {
                    "boundary_context_sources": [
                        {
                            "source_component": "409704",
                            "source_component_tag": "unlabeled graph-only source",
                            "source_component_tag_raw": "L6",
                            "classification": "companion_line_context",
                            "source_hilt_lines": [{"entity_class": "companion_line"}],
                            "reason": "HILT graph connects this source through a companion line.",
                        }
                    ]
                },
            },
            RunConfig(equipment_tag="P3"),
        )

        actions = [step["action"] for step in procedure["ordered_steps"]]
        self.assertTrue(any("Review secondary/context line L6" in action for action in actions))
        context_steps = [step for step in procedure["ordered_steps"] if step.get("secondary_context_tag") == "L6"]
        self.assertEqual(context_steps[0]["secondary_context_line_class"], "companion_line")
        self.assertTrue(context_steps[0]["advisory"])


if __name__ == "__main__":
    unittest.main()
