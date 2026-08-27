import unittest

from domain.feedback import (
    FeedbackCategory,
    FeedbackEffect,
    derivation_effect,
    feedback_category,
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


if __name__ == "__main__":
    unittest.main()
