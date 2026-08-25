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
from sqlalchemy import create_engine, inspect

from api.database import database_url, postgres_config_from_env
from api.db import PostgresRunRepository
from pipeline.env import load_dotenv


APP_TABLES = (
    "external_run_link",
    "isolation_plan",
    "isolation_run_events",
    "isolation_runs",
    "plan_version",
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
