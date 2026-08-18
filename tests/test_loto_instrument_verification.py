import unittest

from loto import _open_gaps, _ordered_steps, _phase_6_verification


class LotoInstrumentVerificationTests(unittest.TestCase):
    def setUp(self):
        self.check = {
            "instrument_id": "0eac545a-deb1-4a0a-a2d1-30d4d5da3022",
            "tag": "PI1755-1HGA30CP001",
            "instrument_type": "pressure_indicator",
            "measured_variable": "pressure",
            "action": "Use PI1755-1HGA30CP001 to verify pressure reaches zero gauge and remains stable.",
            "acceptance_criteria": "Reading is zero gauge pressure and does not reaccumulate.",
        }
        self.instrument_checks = {"verification_before_work": [self.check]}

    def test_pressure_indicator_is_used_as_zero_pressure_verification_method(self):
        phase = _phase_6_verification([], {}, self.instrument_checks)

        self.assertEqual(phase["field_action_required"], [])
        self.assertEqual(phase["instrument_checks"], [self.check])
        steps = _ordered_steps([phase])
        self.assertEqual(steps[0]["instrument_id"], self.check["instrument_id"])
        self.assertIn("verify pressure reaches zero gauge", steps[0]["action"])
        self.assertNotIn("FIELD GAP", steps[0]["action"])

    def test_pressure_indicator_closes_unknown_verification_method_gap_only(self):
        gaps = _open_gaps([], [], [], self.instrument_checks)

        self.assertNotIn("verification_method_unknown", gaps)
        self.assertIn("stored_energy_relief_unknown", gaps)


if __name__ == "__main__":
    unittest.main()
