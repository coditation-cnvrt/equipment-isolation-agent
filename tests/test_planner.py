import unittest

from config import RunConfig
from planner import plan_requests


class PlannerDrawingEvidenceTests(unittest.TestCase):
    def test_required_checks_bind_exact_drawing_candidates_without_resolving_them(self):
        result = plan_requests(
            {
                "context": {"job_id": "1", "project_id": "20", "collection_id": "206"},
                "evidence_state": {
                    "verification_candidate_ids": [],
                    "positive_candidate_ids": ["blind-1"],
                },
                "relief_candidates": {
                    "items": [
                        {
                            "id": "drain-1",
                            "tag": "DRAIN-1",
                            "entity_type": "piping_component",
                            "entity_class": "drain_valve",
                            "bbox": [1, 2, 3, 4],
                        }
                    ]
                },
                "instrument_context": {
                    "instruments": [
                        {
                            "id": "pi-1",
                            "tag": "PI-1",
                            "entity_type": "instrument",
                            "entity_class": "locally_mounted_instrument",
                            "measured_variable": "pressure",
                            "sop_uses": ["verification_support"],
                            "bbox": [5, 6, 7, 8],
                        },
                        {
                            "id": "pt-remote",
                            "entity_type": "instrument",
                            "measured_variable": "pressure",
                            "sop_uses": ["stored_energy_monitoring"],
                        },
                    ]
                },
                "isolation_obligations": {
                    "items": [
                        {
                            "source_type": "process",
                            "status": "isolated",
                            "source_component_tag": "N1",
                            "branch_path_node_ids": ["nozzle-1", "valve-1"],
                        }
                    ]
                },
            },
            RunConfig(equipment_tag="T-1"),
        )

        checks = {item["check_name"]: item for item in result["required_evidence_checks"]}
        self.assertEqual(checks["find_bleeds_vents_drains"]["evidence_targets"][0]["entity_id"], "drain-1")
        self.assertNotIn("find_pressure_indicators", checks)
        self.assertEqual(checks["confirm_zero_pressure"]["evidence_targets"][0]["entity_id"], "pi-1")
        self.assertEqual(checks["find_bypass_paths"]["evidence_targets"][0]["path_node_ids"], ["nozzle-1", "valve-1"])
        self.assertTrue(all(check["status"] == "required" for check in checks.values()))

    def test_terminal_branch_valve_is_bound_as_unconfirmed_release_candidate(self):
        result = plan_requests(
            {
                "evidence_state": {"verification_candidate_ids": [], "positive_candidate_ids": ["blind-1"]},
                "candidates": [
                    {
                        "candidate_id": "drain-valve",
                        "visual_id": "drain-valve",
                        "bbox": [10, 20, 30, 40],
                        "branch_path_node_ids": ["nozzle", "tee", "drain-valve"],
                        "branch_path_node_classes": ["equipment_nozzle", "tee", "gate_valve"],
                    }
                ],
                "_hilt_payload": {
                    "hilt_graph": {
                        "nodes": [
                            {"id": "tee", "payload": {"id": "tee", "entity_class": "tee"}},
                            {"id": "drain-valve", "payload": {"id": "drain-valve", "entity_type": "piping_component", "entity_class": "gate_valve", "text": [{"value": "AA502"}]}},
                            {"id": "flange", "payload": {"id": "flange", "entity_class": "flange"}},
                            {"id": "end", "payload": {"id": "end", "entity_class": "flanged_end"}},
                        ],
                        "links": [
                            {"source": "tee", "target": "drain-valve", "payload": {"entity_type": "process_line"}},
                            {"source": "drain-valve", "target": "flange", "payload": {"entity_type": "process_line"}},
                            {"source": "flange", "target": "end", "payload": {"entity_type": "process_line"}},
                        ],
                    }
                },
            },
            RunConfig(equipment_tag="T-1"),
        )

        check = next(item for item in result["required_evidence_checks"] if item["check_name"] == "find_bleeds_vents_drains")
        target = check["evidence_targets"][0]
        self.assertEqual(target["entity_id"], "drain-valve")
        self.assertEqual(target["tag"], "AA502")
        self.assertEqual(target["acceptance"], "function_and_safe_discharge_confirmation_required")
        self.assertEqual(target["path_node_ids"], ["drain-valve", "flange", "end"])
        self.assertEqual(check["status"], "required")


if __name__ == "__main__":
    unittest.main()
