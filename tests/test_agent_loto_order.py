import unittest

from agent.session import AgentSession
from agent.tools import t_set_isolation_order
from config import RunConfig


def _candidate(candidate_id, available=True):
    return {
        "candidate_id": candidate_id,
        "candidate_label": "gate_valve",
        "properties": {"entity_class": "gate_valve"},
        "source_component_tag": "N1",
        "available_for_isolation": available,
        "availability_status": "available" if available else "unavailable",
    }


class AgentLotoOrderTests(unittest.TestCase):
    def test_order_accepts_only_current_validator_barriers_and_updates_payload(self):
        session = AgentSession(RunConfig(equipment_tag="P3"))
        session.candidate_data = {"candidates": [_candidate("accepted"), _candidate("unavailable", False)]}
        session.validation_data = {
            "assurance_status": "provisional_unproven_isolation",
            "candidates": session.candidate_data["candidates"],
            "isolation_validation": {"barrier_candidate_ids": ["accepted"]},
        }
        session.loto_procedure = {}
        session.final_payload = {"data": [{}]}

        summary = t_set_isolation_order(session, ordered_uuids=["unavailable", "accepted", "unknown"])

        self.assertEqual(summary["accepted_order"], ["accepted"])
        self.assertEqual(summary["ignored_unknown_uuids"], ["unavailable", "unknown"])
        self.assertIs(session.final_payload["data"][0]["loto_procedure"], session.loto_procedure)
        operational = [
            step for step in session.loto_procedure["ordered_steps"]
            if step.get("importance") == "operational" and step.get("device_uuid")
        ]
        self.assertEqual({step["device_uuid"] for step in operational}, {"accepted"})


if __name__ == "__main__":
    unittest.main()
