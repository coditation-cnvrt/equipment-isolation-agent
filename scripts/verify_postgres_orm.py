"""Verify Alembic and SQLAlchemy against a disposable PostgreSQL database.

The configured ``POSTGRES_DB`` is inspected only. The script creates a uniquely
named sibling database, migrates and exercises it, compares both catalogs, and
always drops the disposable database before exiting.

Run with:
    uv run python scripts/verify_postgres_orm.py
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import time
import uuid
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select

from api.database import database_url, postgres_config_from_env
from api.db import PostgresRunRepository, _get_or_create_asset
from api.db_models import PathPoint
from api.models import CreateChangeRequest
from pipeline.env import load_dotenv


APP_TABLES = (
    "asset_reference",
    "audit_event",
    "feedback_application_result",
    "feedback_review_decision",
    "derivation_manifest",
    "derivation_manifest_feedback",
    "external_run_link",
    "finding",
    "input_snapshot",
    "isolation_branch",
    "isolation_point",
    "isolation_plan",
    "isolation_run_events",
    "isolation_runs",
    "path_point",
    "plan_feedback",
    "plan_step",
    "plan_version",
    "plan_version_feedback",
    "work_scope",
    "work_scope_asset",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _catalog_snapshot(engine) -> dict:
    inspector = inspect(engine)
    snapshot = {}
    for table in APP_TABLES:
        snapshot[table] = {
            "columns": sorted(
                (
                    column["name"],
                    str(column["type"]),
                    bool(column["nullable"]),
                    str(column.get("default")),
                )
                for column in inspector.get_columns(table, schema="public")
            ),
            "primary_key": inspector.get_pk_constraint(table, schema="public"),
            "checks": sorted(
                (item.get("name"), " ".join(str(item.get("sqltext") or "").split()))
                for item in inspector.get_check_constraints(table, schema="public")
            ),
            "uniques": sorted(
                (item.get("name"), tuple(item.get("column_names") or ()))
                for item in inspector.get_unique_constraints(table, schema="public")
            ),
            "foreign_keys": sorted(
                (
                    item.get("name"),
                    tuple(item.get("constrained_columns") or ()),
                    item.get("referred_table"),
                    tuple(item.get("referred_columns") or ()),
                    tuple(sorted((item.get("options") or {}).items())),
                )
                for item in inspector.get_foreign_keys(table, schema="public")
            ),
            "indexes": sorted(
                (
                    item.get("name"),
                    bool(item.get("unique")),
                    tuple(item.get("column_names") or ()),
                    tuple(item.get("expressions") or ()),
                    str(item.get("dialect_options") or {}),
                )
                for item in inspector.get_indexes(table, schema="public")
                if not item.get("duplicates_constraint")
            ),
        }
    snapshot["sequences"] = sorted(inspector.get_sequence_names(schema="public"))
    return snapshot


def _repository_smoke(repository: PostgresRunRepository) -> None:
    now = time.time()
    run_id = uuid.uuid4().hex
    run = SimpleNamespace(
        run_id=run_id,
        equipment_tag="ORM-SMOKE-1",
        runner="agentic",
        status="queued",
        created_at=now,
        started_at=None,
        finished_at=None,
        agent=None,
        result=None,
        trace=None,
        error=None,
    )
    request = {
        "equipment_tag": run.equipment_tag,
        "job_id": "9001",
        "job_name": "ORM smoke",
        "cnvrt_project_id": "277",
        "collection_id": "206",
        "unigraph_project_id": "15",
    }
    repository.insert_run(run, request)
    _require(repository.get_run(run_id)["status"] == "queued", "Run insert/get failed")
    _require(
        len(repository.list_runs(job_id="9001", cnvrt_project_id="277")) == 1,
        "Filtered run list failed",
    )

    run.status = "succeeded"
    run.started_at = now + 1
    run.finished_at = now + 2
    run.agent = {"steps_used": 1}
    run.result = {"data": [{"assurance_status": "not_isolated"}]}
    run.trace = [{"tool": "validate"}]
    repository.update_run(run)
    repository.append_event(run_id, {"kind": "status", "payload": {"status": "running"}})
    repository.append_event(run_id, {"kind": "status", "payload": {"status": "succeeded"}})
    _require(
        [item["id"] for item in repository.list_events(run_id, after_id=1)] == [2],
        "Incremental event list failed",
    )

    plan, created = repository.create_plan_from_run(run_id, "ORM smoke area")
    _require(
        created and plan["latest_version"]["source_run"]["run_id"] == run_id,
        "Plan promotion failed",
    )
    duplicate, created_again = repository.create_plan_from_run(run_id)
    _require(
        not created_again and duplicate["plan_id"] == plan["plan_id"],
        "Plan promotion was not idempotent",
    )
    plans, total = repository.list_plans(
        equipment_tag=run.equipment_tag,
        job_id="9001",
        plan_number="ISO-",
    )
    _require(
        total == 1 and plans[0]["plan_id"] == plan["plan_id"],
        "Filtered plan list failed",
    )
    _require(
        repository.get_plan(plan["plan_id"])["versions"][0]["version_no"] == 1,
        "Plan detail failed",
    )

    change = repository.create_change(
        plan["plan_id"],
        CreateChangeRequest(
            raised_against_version_id=plan["latest_plan_version_id"],
            change_type="add_manual_isolation_point",
            target_type="isolation_point",
            target_id="manual-v2",
            justification="Disposable database correction smoke test.",
            source_system="field_review",
            source_reference={"drawing_entity_id": "manual-v2"},
            evidence={"note": "Observed on disposable verification fixture"},
        ),
        "reviewer-1",
    )
    _require(change["feedback_category"] == "manual_observation", "Feedback category inference failed")
    try:
        repository.approve_change(plan["plan_id"], change["change_id"], "reviewer-1")
    except Exception as error:
        _require(getattr(error, "kind", "") == "self_approval_forbidden", "Self approval was not rejected")
    approved = repository.approve_change(plan["plan_id"], change["change_id"], "reviewer-2")
    _require(approved["state"] == "approved", "Correction approval failed")
    _require(len(approved["review_decisions"]) == 1, "Append-only feedback review decision was not recorded")
    prepared = repository.prepare_derivation(plan["plan_id"], plan["latest_plan_version_id"], "reviewer-2")
    failed = SimpleNamespace(
        run_id=uuid.uuid4().hex, equipment_tag=run.equipment_tag, runner="agentic", status="queued",
        created_at=now + 3, started_at=None, finished_at=None, agent=None, result=None, trace=None, error=None,
        parent_run_id=run_id,
    )
    repository.insert_run(failed, prepared["request"])
    failed.status, failed.started_at, failed.finished_at = "failed", now + 3.1, now + 3.2
    failed.error = {"kind": "pipeline_error", "message": "Deliberate correction retry smoke test"}
    repository.update_run(failed)
    _require(repository.list_changes(plan["plan_id"])[0]["state"] == "approved", "Failed derivation consumed approved correction")
    prepared = repository.prepare_derivation(plan["plan_id"], plan["latest_plan_version_id"], "reviewer-2")
    child = SimpleNamespace(
        run_id=uuid.uuid4().hex, equipment_tag=run.equipment_tag, runner="agentic", status="queued",
        created_at=now + 3, started_at=None, finished_at=None, agent=None, result=None, trace=None, error=None,
        parent_run_id=run_id,
    )
    repository.insert_run(child, prepared["request"])
    child.status, child.started_at, child.finished_at = "succeeded", now + 4, now + 5
    child.agent = {"steps_used": 1}
    child.result = {"data": [{"assurance_status": "provisional_unproven_isolation", "isolation_points": [{"uuid": "manual-v2", "tag_number": "XV-MANUAL", "branch_id": "branch-2", "provenance": "manual", "source_paths": [{"branch_id": "branch-2"}, {"branch_id": "branch-3"}]}], "correction_coverage": [{"change_id": change["change_id"], "status": "applied", "reason": "Applied before deterministic validation."}]}]}
    child.trace = [{"tool": "validate"}]
    repository.update_run(child)
    revised = repository.get_plan(plan["plan_id"])
    _require(len(revised["versions"]) == 2 and revised["versions"][0]["parent_plan_version_id"] == plan["latest_plan_version_id"], "Child plan version lineage failed")
    _require(repository.get_run(child.run_id)["parent_run_id"] == run_id, "Child run lineage failed")
    _require(repository.list_changes(plan["plan_id"])[0]["state"] == "applied", "Correction application ledger failed")
    diff = repository.get_plan_version_diff(plan["plan_id"], revised["latest_plan_version_id"])
    _require(diff["summary"]["added"] > 0 and diff["summary"]["safety_significant"] > 0, "Structural version diff failed")
    with repository._session_factory.begin() as session:
        _require(int(session.scalar(select(func.count()).select_from(PathPoint)) or 0) == 2, "Shared isolation point did not persist both branch relationships")
        first = _get_or_create_asset(session, "unigraph_candidate", "reused-vertex", "XV-P15", "gate_valve", {"unigraph_project_id": "15"})
        second = _get_or_create_asset(session, "unigraph_candidate", "reused-vertex", "XV-P27", "gate_valve", {"unigraph_project_id": "27"})
        _require(first.asset_ref_id != second.asset_ref_id, "Asset identities collided across UniGraph projects")


async def _lifespan_smoke() -> None:
    from api.app import create_app

    app = create_app()
    async with app.router.lifespan_context(app):
        pass


def _disposable_name(source_name: str) -> str:
    safe_prefix = re.sub(r"[^a-zA-Z0-9_]", "_", source_name)[:35]
    name = f"{safe_prefix}_orm_verify_{uuid.uuid4().hex[:10]}"
    if not re.fullmatch(r"[a-zA-Z0-9_]+_orm_verify_[0-9a-f]{10}", name):
        raise RuntimeError("Refusing unsafe disposable database name")
    return name


def main() -> int:
    os.chdir(REPO_ROOT)
    load_dotenv()
    source_config = postgres_config_from_env()
    if not source_config.configured:
        raise RuntimeError("PostgreSQL is not configured")

    disposable_name = _disposable_name(source_config.dbname)
    admin_config = replace(source_config, dbname="postgres")
    disposable_config = replace(source_config, dbname=disposable_name)
    admin_engine = create_engine(database_url(admin_config), isolation_level="AUTOCOMMIT")
    quoted_name = admin_engine.dialect.identifier_preparer.quote_identifier(disposable_name)
    created = False

    try:
        command.check(Config(str(REPO_ROOT / "alembic.ini")))
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
        created = True
        os.environ["POSTGRES_DB"] = disposable_name

        alembic_config = Config(str(REPO_ROOT / "alembic.ini"))
        command.upgrade(alembic_config, "head")
        command.check(alembic_config)

        command.downgrade(alembic_config, "base")
        downgrade_engine = create_engine(database_url(disposable_config))
        try:
            downgrade_inspector = inspect(downgrade_engine)
            remaining_tables = set(
                downgrade_inspector.get_table_names(schema="public")
            )
            remaining_sequences = set(
                downgrade_inspector.get_sequence_names(schema="public")
            )
            _require(
                not (set(APP_TABLES) & remaining_tables),
                "Downgrade left application tables behind",
            )
            _require(
                "isolation_plan_number_seq" not in remaining_sequences,
                "Downgrade left the application sequence behind",
            )
        finally:
            downgrade_engine.dispose()

        command.upgrade(alembic_config, "head")
        command.check(alembic_config)

        repository = PostgresRunRepository(disposable_config)
        try:
            repository.check_ready()
            _repository_smoke(repository)
        finally:
            repository.close()
        asyncio.run(_lifespan_smoke())

        source_engine = create_engine(database_url(source_config))
        disposable_engine = create_engine(database_url(disposable_config))
        try:
            if _catalog_snapshot(source_engine) != _catalog_snapshot(disposable_engine):
                raise RuntimeError("Disposable and configured PostgreSQL catalogs differ")
        finally:
            source_engine.dispose()
            disposable_engine.dispose()

        print(f"ORM verification passed; disposable database: {disposable_name}")
        return 0
    finally:
        os.environ["POSTGRES_DB"] = source_config.dbname
        if created:
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (disposable_name,),
                )
                connection.exec_driver_sql(f"DROP DATABASE {quoted_name}")
        admin_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
