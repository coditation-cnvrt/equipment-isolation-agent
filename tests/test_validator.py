import unittest

from equipment_isolation.core.validator import validate


class ValidatorTests(unittest.TestCase):
    def test_manual_review_does_not_mask_missing_barrier_boundary(self):
        result = validate(
            {
                "candidates": [{"candidate_id": "manual-1"}],
                "evidence_state": {
                    "barrier_candidate_ids": [],
                    "manual_review_candidate_ids": ["manual-1"],
                    "missing_boundary_count": 1,
                    "missing_evidence": ["Selected conditional isolation candidate(s) require manual review before acceptance."],
                },
                "required_evidence_checks": [],
            }
        )

        validation = result["isolation_validation"]
        self.assertEqual(validation["assurance_status"], "not_isolated")
        self.assertTrue(validation["terminal"])
        self.assertIn("No selected candidate has deterministic isolation barrier evidence", validation["rationale"])

    def test_missing_boundary_has_one_structured_reason_and_separate_checks(self):
        obligation = {
            "branch_id": "450664:branch:1",
            "source_component": "450664",
            "source_component_tag": "N1_N7",
            "basis": "no_required_isolation_device_found",
            "branch_path_node_ids": ["nozzle", "check-1", "connector"],
            "branch_path_node_classes": ["equipment_nozzle", "check_valve", "off_or_on_page_connector"],
            "branch_context_devices": [
                {
                    "valve_id": "check-1",
                    "entity_type": "piping_component",
                    "entity_class": "check_valve",
                    "tag": "CV-101",
                    "bbox": [10, 20, 30, 40],
                }
            ],
            "terminal_node": {
                "entity_id": "connector",
                "entity_type": "reference",
                "entity_class": "off_or_on_page_connector",
                "display_text": ["PID-0133"],
                "partner_opc": {"id": "", "job_id": "", "job_name": "", "opc_name": ""},
            },
        }
        result = validate(
            {
                "candidates": [{"candidate_id": "barrier-1"}],
                "evidence_state": {
                    "barrier_candidate_ids": ["barrier-1"],
                    "missing_boundary_count": 1,
                    "unresolved_isolation_obligations": [obligation],
                    # Legacy prose duplicates the structured obligation and must
                    # not create another deterministic reason.
                    "missing_evidence": ["1 equipment boundary path(s) do not have a selected isolation candidate."],
                },
                "required_evidence_checks": [
                    {"check_name": "find_bypass_paths", "status": "required", "priority": "medium"}
                ],
            }
        )

        explanation = result["isolation_validation"]["assurance_explanation"]
        self.assertEqual(explanation["summary"], {"primary_reason_count": 1, "outstanding_requirement_count": 1})
        reason = explanation["primary_reasons"][0]
        self.assertEqual(reason["code"], "boundary_path_without_barrier")
        self.assertEqual(reason["boundary_label"], "N1_N7")
        self.assertEqual(reason["terminal"]["partner_mapping_status"], "missing")
        self.assertEqual(reason["terminal"]["terminal_reason"], "unresolved_off_page_connector")
        self.assertEqual(
            reason["encountered_devices"],
            [
                {
                    "entity_id": "check-1",
                    "entity_type": "piping_component",
                    "entity_class": "check_valve",
                    "tag": "CV-101",
                    "bbox": [10, 20, 30, 40],
                    "acceptance": "context_only",
                    "reason": "not_accepted_by_configured_isolation_policy",
                }
            ],
        )
        self.assertEqual(reason["required_action"], "resolve_connector_mapping_and_rerun_validation")
        self.assertEqual(explanation["outstanding_requirements"][0]["check_name"], "find_bypass_paths")

    def test_structured_reasons_are_deduplicated_and_stably_ordered(self):
        obligation = {
            "branch_id": "branch-1",
            "source_component": "source-1",
            "source_component_tag": "N1",
            "basis": "no_required_isolation_device_found",
        }
        result = validate(
            {
                "candidates": [{"candidate_id": "barrier-1"}],
                "evidence_state": {
                    "barrier_candidate_ids": ["barrier-1"],
                    "missing_boundary_count": 2,
                    "unresolved_isolation_obligations": [obligation, dict(obligation)],
                },
                "required_evidence_checks": [
                    {"check_name": "find_pressure_indicators", "status": "required"},
                    {"check_name": "find_bypass_paths", "status": "required"},
                    {"check_name": "find_bypass_paths", "status": "required"},
                ],
            }
        )

        explanation = result["isolation_validation"]["assurance_explanation"]
        self.assertEqual(explanation["summary"], {"primary_reason_count": 1, "outstanding_requirement_count": 2})
        self.assertEqual(
            [item["check_name"] for item in explanation["outstanding_requirements"]],
            ["find_bypass_paths", "find_pressure_indicators"],
        )

    def test_resolved_partner_mapping_requires_partner_traversal_not_remapping(self):
        result = validate(
            {
                "candidates": [{"candidate_id": "barrier-1"}],
                "evidence_state": {
                    "barrier_candidate_ids": ["barrier-1"],
                    "missing_boundary_count": 1,
                    "unresolved_isolation_obligations": [
                        {
                            "branch_id": "branch-1",
                            "source_component": "source-1",
                            "terminal_node": {
                                "entity_id": "opc-1",
                                "entity_class": "Off Or On Page Connector",
                                "partner_opc": {"id": "opc-2", "job_id": "200"},
                            },
                        }
                    ],
                },
                "required_evidence_checks": [],
            }
        )

        reason = result["isolation_validation"]["assurance_explanation"]["primary_reasons"][0]
        self.assertEqual(reason["terminal"]["partner_mapping_status"], "resolved")
        self.assertEqual(reason["required_action"], "traverse_partner_connector_and_rerun_validation")

    def test_aggregate_missing_boundary_does_not_invent_identity(self):
        result = validate(
            {
                "candidates": [{"candidate_id": "barrier-1"}],
                "evidence_state": {
                    "barrier_candidate_ids": ["barrier-1"],
                    "missing_boundary_count": 2,
                },
                "required_evidence_checks": [],
            }
        )

        reason = result["isolation_validation"]["assurance_explanation"]["primary_reasons"][0]
        self.assertEqual(reason["boundary_count"], 2)
        self.assertNotIn("boundary_label", reason)

    def test_complete_validation_has_no_assurance_reasons(self):
        result = validate(
            {
                "candidates": [{"candidate_id": "positive-1"}, {"candidate_id": "verify-1"}],
                "evidence_state": {
                    "barrier_candidate_ids": ["positive-1"],
                    "positive_candidate_ids": ["positive-1"],
                    "verification_candidate_ids": ["verify-1"],
                    "missing_boundary_count": 0,
                },
                "required_evidence_checks": [],
            }
        )

        explanation = result["isolation_validation"]["assurance_explanation"]
        self.assertEqual(result["assurance_status"], "complete_positive_isolation")
        self.assertEqual(explanation["primary_reasons"], [])
        self.assertEqual(explanation["outstanding_requirements"], [])

    def test_manual_review_downgrades_only_after_barrier_coverage_exists(self):
        result = validate(
            {
                "candidates": [{"candidate_id": "manual-1"}],
                "evidence_state": {
                    "barrier_candidate_ids": ["manual-1"],
                    "manual_review_candidate_ids": ["manual-1"],
                    "missing_boundary_count": 0,
                    "missing_evidence": ["Selected conditional isolation candidate(s) require manual review before acceptance."],
                },
                "required_evidence_checks": [],
            }
        )

        validation = result["isolation_validation"]
        self.assertEqual(validation["assurance_status"], "provisional_unproven_isolation")
        self.assertFalse(validation["terminal"])
        self.assertIn("manual review", validation["rationale"])


if __name__ == "__main__":
    unittest.main()
