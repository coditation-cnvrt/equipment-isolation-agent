import os
import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from api.db import postgres_config_from_env
from api.models import IsolationRunRequest
from api.runs import RunStore, event_stream


class _FakeRepository:
    def __init__(self):
        self.runs = {}
        self.events = []

    def insert_run(self, record, request_payload):
        self.runs[record.run_id] = {
            "run_id": record.run_id,
            "equipment_tag": record.equipment_tag,
            "runner": record.runner,
            "status": record.status,
            "created_at": record.created_at,
            "started_at": record.started_at,
            "finished_at": record.finished_at,
            "agent": record.agent,
            "result": record.result,
            "trace": record.trace,
            "error": record.error,
            "request": request_payload,
        }

    def update_run(self, record):
        self.runs[record.run_id].update(
            {
                "status": record.status,
                "started_at": record.started_at,
                "finished_at": record.finished_at,
                "agent": record.agent,
                "result": record.result,
                "trace": record.trace,
                "error": record.error,
            }
        )

    def append_event(self, run_id, event):
        self.events.append({"id": len(self.events) + 1, "run_id": run_id, "event": event})

    def get_run(self, run_id):
        return self.runs.get(run_id)

    def list_runs(self, limit=100, offset=0, **filters):
        rows = sorted(self.runs.values(), key=lambda row: row["created_at"], reverse=True)
        for key, expected in filters.items():
            if key in {"equipment_tag", "status"}:
                rows = [row for row in rows if str(row.get(key) or "") == str(expected)]
            else:
                rows = [row for row in rows if str((row.get("request") or {}).get(key) or "") == str(expected)]
        return rows[offset : offset + limit]

    def list_events(self, run_id, after_id=0):
        return [event for event in self.events if event["run_id"] == run_id and event["id"] > after_id]


class _FailingRepository(_FakeRepository):
    def insert_run(self, record, request_payload):
        raise RuntimeError("database unavailable")

    def update_run(self, record):
        raise RuntimeError("database unavailable")

    def append_event(self, run_id, event):
        raise RuntimeError("database unavailable")

    def list_events(self, run_id, after_id=0):
        raise RuntimeError("database unavailable")


class ApiDbTests(unittest.TestCase):
    def test_postgres_config_uses_separate_env_fields(self):
        old_env = dict(os.environ)
        try:
            os.environ.update(
                {
                    "POSTGRES_HOST": "db",
                    "POSTGRES_PORT": "15432",
                    "POSTGRES_DB": "eqiso",
                    "POSTGRES_USER": "postgres",
                    "POSTGRES_PASSWORD": "secret",
                    "POSTGRES_SSLMODE": "disable",
                }
            )
            config = postgres_config_from_env()
        finally:
            os.environ.clear()
            os.environ.update(old_env)
        self.assertTrue(config.configured)
        self.assertEqual(config.host, "db")
        self.assertEqual(config.port, 15432)
        self.assertEqual(config.dbname, "eqiso")
        self.assertEqual(config.user, "postgres")
        self.assertEqual(config.password, "secret")
        self.assertEqual(config.sslmode, "disable")

    def test_run_store_persists_run_state_to_repository(self):
        repo = _FakeRepository()
        store = RunStore(max_workers=1, repository=repo)
        request = IsolationRunRequest(
            equipment_tag="P3",
            cnvrt_project_id="277",
            collection_id="206",
            unigraph_project_id="15",
        )

        class _Result:
            config = SimpleNamespace(equipment_tag="P3")
            final_payload = {"data": [{"assurance_status": "not_isolated"}]}
            agent_result = {"steps_used": 1, "forced": [], "assurance_status": "not_isolated"}
            trace = [{"tool": "validate"}]

        with mock.patch("api.service.run_agent_pipeline", return_value=_Result()):
            record = store.create(request, "token")
            for _ in range(100):
                snapshot = store.snapshot(store.get(record.run_id))
                if snapshot["status"] == "succeeded":
                    break
                time.sleep(0.01)
        persisted = repo.get_run(record.run_id)
        self.assertEqual(persisted["status"], "succeeded")
        self.assertEqual(persisted["request"]["equipment_tag"], "P3")
        self.assertNotIn("auth_token", persisted["request"])
        self.assertEqual(persisted["result"]["data"][0]["assurance_status"], "not_isolated")
        self.assertNotIn("result", store.list()[0])
        for _ in range(100):
            with store._lock:
                retained = record.run_id in store._records
            if not retained:
                break
            time.sleep(0.01)
        self.assertFalse(retained)
        reloaded = store.get(record.run_id)
        self.assertIsNot(reloaded, record)
        self.assertEqual(reloaded.status, "succeeded")
        self.assertEqual(reloaded.result["data"][0]["assurance_status"], "not_isolated")
        store.shutdown()

    def test_repository_insert_failure_rejects_run_creation(self):
        store = RunStore(max_workers=1, repository=_FailingRepository())
        request = IsolationRunRequest(
            equipment_tag="P3",
            cnvrt_project_id="277",
            collection_id="206",
            unigraph_project_id="15",
        )
        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            store.create(request, "token")
        store.shutdown()

    def test_shutdown_marks_nonterminal_rows_failed_instead_of_deleting_them(self):
        repo = _FakeRepository()
        release = threading.Event()
        started = threading.Event()
        store = RunStore(max_workers=1, repository=repo)
        first = IsolationRunRequest(
            equipment_tag="P3", cnvrt_project_id="277", collection_id="206", unigraph_project_id="15"
        )
        second = IsolationRunRequest(
            equipment_tag="P4", cnvrt_project_id="277", collection_id="206", unigraph_project_id="15"
        )

        def stuck(*_, **__):
            started.set()
            release.wait(5)
            return {"ok": True, "payload": {"data": []}, "agent": {}, "trace": []}

        try:
            with mock.patch("api.runs.execute_agent_request", side_effect=stuck):
                running = store.create(first, "token")
                queued = store.create(second, "token")
                self.assertTrue(started.wait(1))
                store.shutdown()
            self.assertEqual(repo.get_run(running.run_id)["status"], "failed")
            self.assertEqual(repo.get_run(queued.run_id)["status"], "failed")
            self.assertEqual(repo.get_run(running.run_id)["error"]["kind"], "server_shutdown")
            self.assertEqual(repo.get_run(queued.run_id)["error"]["kind"], "server_shutdown")
        finally:
            release.set()

    def test_run_store_does_not_discover_file_backed_runs(self):
        store = RunStore(max_workers=1)
        self.assertEqual(store.list(), [])
        self.assertIsNone(store.get("b" * 32))
        store.shutdown()

    def test_event_stream_reads_events_from_repository(self):
        repo = _FakeRepository()
        record = SimpleNamespace(run_id="r1", status="failed", events=None)
        repo.events.append(
            {"id": 1, "run_id": "r1", "event": {"kind": "tool_call", "payload": {"name": "fetch_boundary"}}}
        )
        frames = list(event_stream(record, repository=repo))
        self.assertIn("fetch_boundary", frames[0])
        self.assertIn("event: done", frames[-1])

    def test_event_stream_does_not_hide_repository_failure(self):
        record = SimpleNamespace(run_id="r1", status="failed", events=None)
        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            list(event_stream(record, repository=_FailingRepository()))


if __name__ == "__main__":
    unittest.main()
