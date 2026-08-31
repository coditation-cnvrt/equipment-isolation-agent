import unittest

from equipment_isolation.domain.feedback import (
    FeedbackCategory,
    FeedbackEffect,
    PointFeedbackState,
    allowed_point_feedback_types,
    derivation_effect,
    feedback_category,
    feedback_transition_group,
    point_feedback_state,
    validate_feedback_category,
)


class FeedbackDefinitionTests(unittest.TestCase):
    def test_existing_feedback_types_have_one_authoritative_category(self):
        self.assertEqual(
            feedback_category("correct_label"),
            FeedbackCategory.INPUT_CORRECTION,
        )
        self.assertEqual(
            feedback_category("add_manual_isolation_point"),
            FeedbackCategory.MANUAL_OBSERVATION,
        )

    def test_category_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "belongs to category"):
            validate_feedback_category("correct_label", "manual_observation")

    def test_unsupported_future_category_has_no_accidental_derivation_path(self):
        with self.assertRaisesRegex(ValueError, "Unsupported feedback type"):
            derivation_effect("approve_requirement_deviation")

    def test_registered_types_publish_a_typed_derivation_effect(self):
        self.assertEqual(
            derivation_effect("mark_point_unavailable"),
            FeedbackEffect.INPUT_OVERLAY,
        )
        self.assertEqual(
            derivation_effect("confirm_bypass"),
            FeedbackEffect.MANUAL_OBSERVATION_OVERLAY,
        )

    def test_point_state_controls_contextual_actions(self):
        accepted = {"feedback_state": "accepted"}
        manual = {"feedback_state": "manual_review"}
        excluded = {"feedback_state": "excluded"}
        unavailable = {"feedback_state": "accepted", "available_for_isolation": False}

        self.assertEqual(point_feedback_state(accepted), PointFeedbackState.ACCEPTED)
        self.assertNotIn("accept_manual_candidate", allowed_point_feedback_types(accepted))
        self.assertNotIn("confirm_bypass", allowed_point_feedback_types(accepted))
        self.assertIn("accept_manual_candidate", allowed_point_feedback_types(manual))
        self.assertIn("confirm_bypass", allowed_point_feedback_types(manual))
        self.assertNotIn("reject_manual_candidate", allowed_point_feedback_types(excluded))
        self.assertEqual(
            allowed_point_feedback_types(unavailable),
            frozenset({"correct_label", "mark_point_available"}),
        )

    def test_selection_actions_share_one_pending_transition_group(self):
        self.assertEqual(feedback_transition_group("accept_manual_candidate"), "selection")
        self.assertEqual(feedback_transition_group("reject_manual_candidate"), "selection")
        self.assertEqual(feedback_transition_group("confirm_bypass"), "selection")


if __name__ == "__main__":
    unittest.main()
