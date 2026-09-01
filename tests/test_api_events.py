import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from equipment_isolation.api.events import asset_condition_event_stream, compact_event, sse_frame
from equipment_isolation.api.runs import event_stream


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


class _AssetEventRepository:
    def latest_asset_condition_event_id(self, _context):
        return "previous-event"

    def list_asset_condition_events(
        self, _context, *, after_id="", exclude_ids=None, limit=100
    ):
        if after_id != "previous-event":
            return []
        return [{
            "event_id": "next-event",
            "type": "asset_condition.changed",
            "event_type": "cleared",
            "condition_id": "condition-1",
            "state": "cleared",
            "occurred_at": "2026-09-01T00:00:00Z",
            "asset": {"external_id": "valve-1"},
            "payload": {},
        }]


class _LateCommitAssetEventRepository:
    def asset_condition_event_replay_state(self, _context, _after_id=""):
        return {
            "cursor_id": "later-visible-event",
            "cursor_occurred_at": datetime(2026, 9, 1, 0, 0, 2, tzinfo=timezone.utc),
            "seen_ids": {"later-visible-event"},
        }

    def list_asset_condition_events(
        self, _context, *, after_id="", exclude_ids=None, limit=100
    ):
        return [
            {
                "event_id": "late-commit-earlier-timestamp",
                "type": "asset_condition.changed",
                "event_type": "reported",
                "condition_id": "condition-2",
                "state": "active",
                "occurred_at": datetime(2026, 9, 1, 0, 0, 1, tzinfo=timezone.utc),
                "asset": {"external_id": "valve-2"},
                "payload": {},
            },
            {
                "event_id": "later-visible-event",
                "type": "asset_condition.changed",
                "event_type": "reported",
                "condition_id": "condition-1",
                "state": "active",
                "occurred_at": datetime(2026, 9, 1, 0, 0, 2, tzinfo=timezone.utc),
                "asset": {"external_id": "valve-1"},
                "payload": {},
            },
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

    def test_asset_condition_stream_starts_at_current_cursor_and_emits_durable_ids(self):
        stream = asset_condition_event_stream(
            _AssetEventRepository(),
            {"cnvrt_project_id": "277", "collection_id": "206", "unigraph_project_id": "15", "job_id": "2151"},
            poll_interval=0,
        )
        try:
            ready = next(stream)
            changed = next(stream)
        finally:
            stream.close()
        self.assertIn("event: ready", ready)
        self.assertIn("id: next-event", changed)
        self.assertIn("event: asset_condition.changed", changed)

    def test_asset_condition_stream_emits_late_commit_without_replaying_seen_event(self):
        stream = asset_condition_event_stream(
            _LateCommitAssetEventRepository(),
            {"cnvrt_project_id": "277", "collection_id": "206", "unigraph_project_id": "15"},
            last_event_id="later-visible-event",
            poll_interval=0,
        )
        try:
            next(stream)
            changed = next(stream)
        finally:
            stream.close()
        self.assertIn("id: late-commit-earlier-timestamp", changed)
        self.assertNotIn("id: later-visible-event", changed)


if __name__ == "__main__":
    unittest.main()
