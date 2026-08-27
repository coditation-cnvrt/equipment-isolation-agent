import unittest
from types import SimpleNamespace
from unittest import mock

from agent.tools import t_find_candidates, t_resolve_bboxes
from domain.corrections import apply_approved_corrections
from evidence import candidate_flags


def candidate(candidate_id="v1", decision="conditional_manual_review"):
    return {
        "candidate_id": candidate_id,
        "tag_number": "XV-1",
        "policy_decision": decision,
        "requires_manual_review": decision == "conditional_manual_review",
        "classification": {
            "decision": decision,
            "raw_entity_class": "undefined_valve",
            "class_values": ["undefined_valve"],
            "is_barrier": False,
            "is_positive_isolation": False,
        },
    }


def correction(kind, target="v1", **proposed):
    return {"change_id": f"change-{kind}", "change_type": kind, "target_id": target, "proposed_change": proposed, "justification": "Reviewed in field", "raised_by": "1", "approved_by": "2"}


class CorrectionApplicationTests(unittest.TestCase):
    def test_agent_applies_corrections_after_authoritative_resolution(self):
        approved = [correction("correct_label", label="XV-AUTHORITATIVE")]
        session = SimpleNamespace(
            boundary_data={"boundary": True},
            candidate_data=None,
            bbox_data=None,
            config=SimpleNamespace(policy=object(), approved_corrections=approved, resolved_job_id="2100", job_name="drawing"),
            infer_job_from_candidates=lambda: False,
        )
        graph_result = {"candidates": [candidate()], "_candidate_pool": [candidate()], "debug": {}}
        hilt_result = {"candidates": [candidate()], "_candidate_pool": [candidate()], "debug": {}}
        with mock.patch("agent.tools._fatal_job_resolution", return_value={}), mock.patch(
            "agent.tools.find_candidates", return_value=graph_result
        ), mock.patch("agent.tools._summarize_candidates", return_value={}):
            t_find_candidates(session)
        self.assertEqual(session.candidate_data["candidates"][0]["tag_number"], "XV-1")

        with mock.patch("agent.tools.resolve_bboxes", return_value=hilt_result), mock.patch(
            "agent.tools._summarize_bbox", return_value={}
        ):
            t_resolve_bboxes(session)
        self.assertEqual(session.bbox_data["candidates"][0]["tag_number"], "XV-AUTHORITATIVE")
        self.assertEqual(session.bbox_data["correction_coverage"][0]["status"], "applied")

    def test_accept_manual_candidate_is_revalidated_as_manual_provenance(self):
        result = apply_approved_corrections({"candidates": [candidate()], "_candidate_pool": [], "debug": {}}, [correction("accept_manual_candidate")])
        accepted = result["candidates"][0]
        self.assertEqual(accepted["policy_decision"], "automatic")
        self.assertEqual(accepted["provenance"], "manual")
        self.assertFalse(accepted["requires_manual_review"])
        self.assertEqual(result["correction_coverage"][0]["status"], "applied")

    def test_deterministic_candidate_cannot_be_rejected(self):
        result = apply_approved_corrections({"candidates": [candidate(decision="automatic")], "debug": {}}, [correction("reject_manual_candidate")])
        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["correction_coverage"][0]["status"], "failed")

    def test_manual_addition_must_exist_in_fresh_candidate_pool(self):
        pooled = candidate("v2")
        result = apply_approved_corrections({"candidates": [], "_candidate_pool": [pooled], "debug": {}}, [correction("add_manual_isolation_point", "v2")])
        self.assertEqual([item["candidate_id"] for item in result["candidates"]], ["v2"])
        missing = apply_approved_corrections({"candidates": [], "_candidate_pool": [], "debug": {}}, [correction("add_manual_isolation_point", "missing")])
        self.assertEqual(missing["correction_coverage"][0]["status"], "failed")

    def test_manual_addition_resolves_exact_hilt_drawing_identity(self):
        pooled = {**candidate("graph-v2"), "visual_node_id": "hilt-v2", "visual_id": "source-v2"}
        result = apply_approved_corrections(
            {"candidates": [], "_candidate_pool": [pooled], "debug": {}},
            [correction("add_manual_isolation_point", "hilt-v2")],
        )
        self.assertEqual([item["candidate_id"] for item in result["candidates"]], ["graph-v2"])
        self.assertEqual(result["correction_coverage"][0]["status"], "applied")

    def test_manual_addition_does_not_duplicate_candidate_already_rediscovered(self):
        rediscovered = {**candidate("graph-v2"), "visual_node_id": "hilt-v2"}
        result = apply_approved_corrections(
            {"candidates": [rediscovered], "_candidate_pool": [rediscovered], "debug": {}},
            [correction("add_manual_isolation_point", "hilt-v2")],
        )
        self.assertEqual([item["candidate_id"] for item in result["candidates"]], ["graph-v2"])
        self.assertEqual(result["correction_coverage"][0]["status"], "applied")

    def test_manual_addition_rejects_ambiguous_drawing_identity(self):
        pool = [
            {**candidate("graph-v2"), "visual_node_id": "shared-hilt"},
            {**candidate("graph-v3"), "visual_id": "shared-hilt"},
        ]
        result = apply_approved_corrections(
            {"candidates": [], "_candidate_pool": pool, "debug": {}},
            [correction("add_manual_isolation_point", "shared-hilt")],
        )
        self.assertEqual(result["candidates"], [])
        self.assertEqual(result["correction_coverage"][0]["status"], "failed")
        self.assertIn("multiple candidates", result["correction_coverage"][0]["reason"])

    def test_label_and_bypass_corrections_preserve_identity(self):
        result = apply_approved_corrections({"candidates": [candidate()], "debug": {}}, [correction("correct_label", label="XV-101"), correction("confirm_bypass")])
        point = result["candidates"][0]
        self.assertEqual(point["candidate_id"], "v1")
        self.assertEqual(point["tag_number"], "XV-101")
        self.assertTrue(point["required_branch_isolation"])

    def test_feedback_category_mismatch_cannot_reach_candidate_logic(self):
        mismatched = correction("correct_label", label="XV-101")
        mismatched["feedback_category"] = "manual_observation"
        result = apply_approved_corrections(
            {"candidates": [candidate()], "debug": {}},
            [mismatched],
        )
        self.assertEqual(result["candidates"][0]["tag_number"], "XV-1")
        self.assertEqual(result["correction_coverage"][0]["status"], "failed")
        self.assertIn("belongs to category", result["correction_coverage"][0]["reason"])

    def test_unavailable_point_remains_auditable_but_cannot_be_a_barrier(self):
        available = candidate(decision="automatic")
        available["classification"]["is_barrier"] = True
        result = apply_approved_corrections(
            {"candidates": [available], "_candidate_pool": [available], "debug": {}},
            [correction("mark_point_unavailable")],
        )

        point = result["candidates"][0]
        self.assertEqual(point["availability_status"], "unavailable")
        self.assertFalse(point["available_for_isolation"])
        self.assertEqual(point["unavailable_reason"], "Reviewed in field")
        self.assertEqual(candidate_flags(point), {"barrier": False, "positive": False, "verification": False})
        self.assertEqual(result["correction_coverage"][0]["status"], "applied")

    def test_later_return_to_service_supersedes_unavailable_state(self):
        available = candidate(decision="automatic")
        available["classification"]["is_barrier"] = True
        result = apply_approved_corrections(
            {"candidates": [available], "_candidate_pool": [available], "debug": {}},
            [correction("mark_point_unavailable"), correction("mark_point_available")],
        )

        point = result["candidates"][0]
        self.assertEqual(point["availability_status"], "available")
        self.assertTrue(point["available_for_isolation"])
        self.assertNotIn("unavailable_reason", point)
        self.assertTrue(candidate_flags(point)["barrier"])

    def test_unavailable_hilt_point_preserves_existing_plan_point_identity(self):
        pooled = {**candidate("graph-v1", decision="automatic"), "visual_node_id": "hilt-v1"}
        result = apply_approved_corrections(
            {"candidates": [], "_candidate_pool": [pooled], "debug": {}},
            [correction("mark_point_unavailable", "hilt-v1")],
        )

        point = result["candidates"][0]
        self.assertEqual(point["candidate_id"], "graph-v1")
        self.assertEqual(point["plan_point_id"], "hilt-v1")


if __name__ == "__main__":
    unittest.main()
