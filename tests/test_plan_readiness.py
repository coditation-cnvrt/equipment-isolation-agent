import unittest

from domain.plan_readiness import build_plan_readiness
from validator import validate


class PlanReadinessTests(unittest.TestCase):
    def test_field_holds_do_not_make_plan_incomplete(self):
        checks = [
            {
                "check_name": "find_bypass_paths",
                "status": "required",
                "reason": "Review alternate routes.",
                "completion_context": "pre_job_review",
                "blocks_plan_readiness": False,
                "responsible_role": "authorized_field_personnel",
                "method_identified": True,
                "loto_phase": 1,
            },
            {
                "check_name": "find_bleeds_vents_drains",
                "status": "required",
                "reason": "Confirm the identified bleed and safe discharge.",
                "completion_context": "field_execution",
                "blocks_plan_readiness": False,
                "responsible_role": "authorized_field_personnel",
                "method_identified": True,
                "loto_phase": 5,
                "evidence_targets": [{"entity_id": "aa502", "tag": "AA502"}],
            },
            {
                "check_name": "confirm_zero_pressure",
                "status": "required",
                "reason": "Verify zero pressure and no reaccumulation.",
                "completion_context": "field_execution",
                "blocks_plan_readiness": False,
                "responsible_role": "authorized_field_personnel",
                "method_identified": True,
                "loto_phase": 6,
                "evidence_targets": [{"entity_id": "pi1755", "tag": "PI-1755"}],
            },
        ]
        result = validate(
            {
                "candidates": [{"candidate_id": "barrier-1"}],
                "evidence_state": {
                    "barrier_candidate_ids": ["barrier-1"],
                    "missing_boundary_count": 0,
                    "expected_boundary_count": 15,
                    "covered_boundary_source_count": 15,
                },
                "required_evidence_checks": checks,
            }
        )

        self.assertEqual(result["assurance_status"], "provisional_unproven_isolation")
        readiness = result["plan_readiness"]
        self.assertEqual(readiness["status"], "ready_for_field_review")
        self.assertTrue(readiness["planning_complete"])
        self.assertEqual(
            readiness["summary"],
            {"planning_blocker_count": 0, "pre_job_review_count": 1, "field_hold_point_count": 2},
        )
        self.assertEqual([item["loto_phase"] for item in readiness["field_execution_hold_points"]], [5, 6])

    def test_missing_verification_method_blocks_plan_readiness(self):
        result = validate(
            {
                "candidates": [{"candidate_id": "barrier-1"}],
                "evidence_state": {"barrier_candidate_ids": ["barrier-1"], "missing_boundary_count": 0},
                "required_evidence_checks": [
                    {
                        "check_name": "find_pressure_indicators",
                        "status": "required",
                        "reason": "Identify an approved zero-energy verification method.",
                        "completion_context": "planning",
                        "blocks_plan_readiness": True,
                        "method_identified": False,
                    }
                ],
            }
        )

        self.assertEqual(result["plan_readiness"]["status"], "incomplete")
        self.assertEqual(result["plan_readiness"]["summary"]["planning_blocker_count"], 1)

    def test_missing_boundary_is_always_a_planning_blocker(self):
        explanation = {
            "primary_reasons": [
                {
                    "reason_id": "boundary_path_without_barrier:branch-1",
                    "code": "boundary_path_without_barrier",
                }
            ],
            "outstanding_requirements": [],
        }
        readiness = build_plan_readiness(
            assurance_status="not_isolated",
            assurance_explanation=explanation,
            unresolved_checks=[],
        )

        self.assertEqual(readiness["status"], "incomplete")
        self.assertFalse(readiness["planning_complete"])
        self.assertEqual(readiness["summary"]["planning_blocker_count"], 1)


if __name__ == "__main__":
    unittest.main()
