import json
import unittest
from types import SimpleNamespace

from api.events import compact_event, sse_frame
from api.runs import event_stream


class _EventRepository:
    def list_events(self, run_id, after_id=0):
        if after_id:
            return []
        return [
            {
                "id": 1,
                "event": {"kind": "tool_call", "payload": {"name": "fetch_boundary"}},
            }
        ]


class ApiEventTests(unittest.TestCase):
    def test_tool_result_events_are_compact(self):
        event = compact_event(
            "tool_result",
            {
                "name": "validate",
                "result": {
                    "assurance_status": "not_isolated",
                    "missing_boundary_count": 2,
                    "large_payload": ["x"] * 100,
                },
            },
        )
        self.assertEqual(event["payload"]["name"], "validate")
        self.assertEqual(event["payload"]["result"]["missing_boundary_count"], 2)
        self.assertNotIn("large_payload", event["payload"]["result"])

    def test_sse_frame_is_json_data(self):
        frame = sse_frame("done", {"status": "succeeded"})
        self.assertTrue(frame.startswith("event: done\n"))
        data = frame.split("data: ", 1)[1].strip()
        self.assertEqual(json.loads(data), {"status": "succeeded"})

    def test_event_stream_replays_database_events_for_each_subscriber(self):
        repository = _EventRepository()
        record = SimpleNamespace(run_id="r1", status="succeeded", events=None)
        first = list(event_stream(record, repository=repository))
        second = list(event_stream(record, repository=repository))
        self.assertEqual(first, second)
        self.assertIn("fetch_boundary", first[0])
        self.assertIn("event: done", first[-1])


if __name__ == "__main__":
    unittest.main()
