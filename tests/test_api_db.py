import os
import threading
import time
import unittest
from contextlib import contextmanager
from importlib.resources import files
from types import SimpleNamespace
from unittest import mock

from equipment_isolation.api.db import (
    PostgresConfig,
    PostgresRunRepository,
    _asset_scope_key,
    _migration_config,
    _plan_number_statement,
    migration_head_revision,
    postgres_config_from_env,
)
from equipment_isolation.api.db_models import Base, IsolationRun
from equipment_isolation.api.models import IsolationRunRequest
from equipment_isolation.api.runs import RunStore, event_stream
from sqlalchemy import select
from sqlalchemy.dialects import postgresql


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
    @staticmethod
    def _ready_repository(tables, current_heads, columns=()):
        connection = mock.MagicMock()
        connection_context = mock.MagicMock()
        connection_context.__enter__.return_value = connection
        engine = mock.MagicMock()
        engine.connect.return_value = connection_context
        repository = PostgresRunRepository(
            PostgresConfig(host="db", port=5432, dbname="eqiso", user="app", password=""),
            engine=engine,
        )
        inspector = mock.MagicMock()
        inspector.get_table_names.return_value = tables
        inspector.get_columns.return_value = columns
        migration_context = mock.MagicMock()
        migration_context.get_current_heads.return_value = current_heads

        @contextmanager
        def patched_inspection():
            with mock.patch("equipment_isolation.api.db.inspect", return_value=inspector), mock.patch(
                "alembic.runtime.migration.MigrationContext.configure",
                return_value=migration_context,
            ):
                yield

        return repository, patched_inspection()

    def test_packaged_migration_has_one_expected_head(self):
        self.assertEqual(migration_head_revision(), "0005_feedback_constraint_names")

    def test_migration_config_and_template_are_package_resources(self):
        migration_package = files("equipment_isolation.api.migrations")
        self.assertTrue(migration_package.joinpath("alembic.ini").is_file())
        self.assertTrue(migration_package.joinpath("script.py.mako").is_file())
        self.assertTrue(
            migration_package.joinpath(
                "versions", "0001_current_schema.py"
            ).is_file()
        )
        self.assertTrue(migration_package.joinpath("versions", "0002_plan_corrections.py").is_file())
        self.assertTrue(migration_package.joinpath("versions", "0003_scoped_asset_identity.py").is_file())
        self.assertTrue(migration_package.joinpath("versions", "0004_plan_feedback_framework.py").is_file())
        self.assertTrue(migration_package.joinpath("versions", "0005_feedback_constraint_names.py").is_file())
        self.assertEqual(
            _migration_config().get_main_option("script_location"),
            str(migration_package),
        )

    def test_orm_metadata_owns_all_application_tables(self):
        self.assertEqual(
            set(Base.metadata.tables),
            {"isolation_runs", "isolation_run_events", "isolation_plan", "plan_version", "external_run_link", "asset_reference", "work_scope", "work_scope_asset", "input_snapshot", "isolation_branch", "isolation_point", "path_point", "plan_step", "finding", "plan_feedback", "feedback_review_decision", "derivation_manifest", "derivation_manifest_feedback", "plan_version_feedback", "feedback_application_result", "audit_event"},
        )
        self.assertIn("isolation_plan_number_seq", Base.metadata._sequences)

    def test_postgresql_statements_preserve_json_index_and_lock_semantics(self):
        dialect = postgresql.dialect()
        json_filter = str(
            select(IsolationRun.run_id)
            .where(IsolationRun.request["job_id"].astext == "9001")
            .compile(dialect=dialect)
        )
        locked_run = str(
            select(IsolationRun)
            .where(IsolationRun.run_id == "a" * 32)
            .with_for_update()
            .compile(dialect=dialect)
        )
        plan_number = str(_plan_number_statement().compile(dialect=dialect))
        self.assertIn("->>", json_filter)
        self.assertNotIn("CAST", json_filter)
        self.assertIn("FOR UPDATE", locked_run)
        self.assertIn("nextval('isolation_plan_number_seq')", plan_number)

    def test_repository_readiness_accepts_current_migration_head(self):
        tables = (
            "alembic_version",
            "isolation_runs",
            "isolation_run_events",
            "isolation_plan",
            "plan_version",
            "external_run_link",
        )
        repository, connection_patch = self._ready_repository(tables, ("0005_feedback_constraint_names",))
        with connection_patch:
            repository.check_ready()

    def test_repository_readiness_rejects_outdated_migration(self):
        tables = (
            "alembic_version",
            "isolation_runs",
            "isolation_run_events",
            "isolation_plan",
            "plan_version",
            "external_run_link",
        )
        repository, connection_patch = self._ready_repository(tables, ("old_revision",))
        with connection_patch, self.assertRaisesRegex(RuntimeError, "expected 0005_feedback_constraint_names"):
            repository.check_ready()

    def test_asset_scope_separates_reused_external_ids(self):
        first = _asset_scope_key("unigraph_candidate", {"unigraph_project_id": "15"})
        second = _asset_scope_key("unigraph_candidate", {"unigraph_project_id": "27"})
        drawing = _asset_scope_key("cnvrt_drawing_entity", {"cnvrt_project_id": "277", "collection_id": "206", "job_id": "2100"})
        self.assertEqual(first, "unigraph:15")
        self.assertNotEqual(first, second)
        self.assertEqual(drawing, "cnvrt:277:collection:206:job:2100")

    def test_repository_readiness_rejects_unversioned_current_schema(self):
        tables = (
            "alembic_version",
            "isolation_runs",
            "isolation_run_events",
            "isolation_plan",
            "plan_version",
            "external_run_link",
        )
        repository, connection_patch = self._ready_repository(tables, ())
        with connection_patch, self.assertRaisesRegex(RuntimeError, "unversioned"):
            repository.check_ready()

    def test_repository_readiness_rejects_legacy_run_columns(self):
        tables = (
            "alembic_version",
            "isolation_runs",
            "isolation_run_events",
            "isolation_plan",
            "plan_version",
            "external_run_link",
        )
        repository, connection_patch = self._ready_repository(
            tables,
            ("0001_current_schema",),
            ({"name": "run_id"}, {"name": "artifacts"}),
        )
        with connection_patch, self.assertRaisesRegex(RuntimeError, "legacy"):
            repository.check_ready()

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

        with mock.patch("equipment_isolation.api.service.run_agent_pipeline", return_value=_Result()):
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
            with mock.patch("equipment_isolation.api.runs.execute_agent_request", side_effect=stuck):
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
