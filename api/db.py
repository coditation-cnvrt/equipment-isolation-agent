"""Minimal Postgres access layer for API run persistence."""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.session import jsonable
from api.plans import (
    PlanDomainError,
    canonical_hash,
    derivation_status,
    model_fingerprint,
    validate_promotable_result,
)


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str
    sslmode: str = "prefer"

    @property
    def configured(self) -> bool:
        return bool(self.host and self.dbname and self.user)


def postgres_config_from_env() -> PostgresConfig:
    return PostgresConfig(
        host=os.environ.get("POSTGRES_HOST", "").strip(),
        port=int(os.environ.get("POSTGRES_PORT") or "5432"),
        dbname=os.environ.get("POSTGRES_DB", "").strip(),
        user=os.environ.get("POSTGRES_USER", "").strip(),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        sslmode=os.environ.get("POSTGRES_SSLMODE", "prefer").strip() or "prefer",
    )


def postgres_configured() -> bool:
    return postgres_config_from_env().configured


def auto_init_schema_on_startup() -> bool:
    return os.environ.get("EIA_AUTO_INIT_SCHEMA_ON_STARTUP", "").strip().lower() in {"1", "true", "yes", "on"}


def _connect_kwargs(config: PostgresConfig) -> dict[str, Any]:
    return {
        "host": config.host,
        "port": config.port,
        "dbname": config.dbname,
        "user": config.user,
        "password": config.password,
        "sslmode": config.sslmode,
    }


def _connect(config: PostgresConfig | None = None):
    import psycopg

    config = config or postgres_config_from_env()
    return psycopg.connect(**_connect_kwargs(config))


def init_schema(config: PostgresConfig | None = None, schema_path: str | Path = "schema.sql") -> None:
    sql = Path(schema_path).read_text(encoding="utf-8")
    with _connect(config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def _pool_max_size() -> int:
    return int(os.environ.get("POSTGRES_POOL_MAX_SIZE") or "8")


def _pool_timeout() -> float:
    return float(os.environ.get("POSTGRES_POOL_TIMEOUT_SECONDS") or "5")


class PostgresRunRepository:
    def __init__(self, config: PostgresConfig | None = None):
        self.config = config or postgres_config_from_env()
        self._pool = None
        self._pool_lock = threading.Lock()

    @contextmanager
    def _connection(self):
        with self._get_pool().connection() as conn:
            yield conn

    def _get_pool(self):
        if self._pool is None:
            with self._pool_lock:
                if self._pool is None:
                    from psycopg_pool import ConnectionPool

                    self._pool = ConnectionPool(
                        "",
                        kwargs=_connect_kwargs(self.config),
                        min_size=0,
                        max_size=_pool_max_size(),
                        timeout=_pool_timeout(),
                    )
        return self._pool

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    def check_ready(self) -> None:
        """Fail unless the database is reachable and the required schema exists."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT to_regclass('public.isolation_runs'),
                           to_regclass('public.isolation_run_events'),
                           to_regclass('public.isolation_plan'),
                           to_regclass('public.plan_version'),
                           to_regclass('public.external_run_link')
                    """
                )
                tables = cur.fetchone()
                cur.execute(
                    """
                    SELECT count(*)
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'isolation_runs'
                      AND column_name IN ('artifacts', 'run_dir')
                    """
                )
                legacy_run_columns = int(cur.fetchone()[0])
        if not tables or any(table is None for table in tables):
            raise RuntimeError("PostgreSQL is reachable but the equipment-isolation schema is incomplete")
        if legacy_run_columns:
            raise RuntimeError("PostgreSQL still has legacy local-artifact columns; recreate it from the current schema.sql")

    def insert_run(self, record, request_payload: dict) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO isolation_runs (
                        run_id, equipment_tag, runner, status, created_at, started_at,
                        finished_at, request, agent, result, trace, error
                    )
                    VALUES (
                        %(run_id)s, %(equipment_tag)s, %(runner)s, %(status)s, %(created_at)s,
                        %(started_at)s, %(finished_at)s, %(request)s::jsonb, %(agent)s::jsonb,
                        %(result)s::jsonb, %(trace)s::jsonb, %(error)s::jsonb
                    )
                    """,
                    _record_params(record, request_payload=request_payload),
                )
            conn.commit()

    def update_run(self, record) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE isolation_runs
                    SET status = %(status)s,
                        started_at = %(started_at)s,
                        finished_at = %(finished_at)s,
                        agent = %(agent)s::jsonb,
                        result = %(result)s::jsonb,
                        trace = %(trace)s::jsonb,
                        error = %(error)s::jsonb
                    WHERE run_id = %(run_id)s
                    """,
                    _record_params(record),
                )
            conn.commit()

    def append_event(self, run_id: str, event: dict) -> None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO isolation_run_events (run_id, event)
                    VALUES (%s, %s::jsonb)
                    """,
                    (run_id, _json(event)),
                )
            conn.commit()

    def get_run(self, run_id: str) -> dict | None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT run_id, equipment_tag, runner, status, created_at, started_at,
                           finished_at, agent, request, result, trace, error
                    FROM isolation_runs
                    WHERE run_id = %s
                    """,
                    (run_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return _row_to_dict(row)

    def list_runs(
        self,
        limit: int = 100,
        offset: int = 0,
        equipment_tag: str | None = None,
        status: str | None = None,
        job_id: str | None = None,
        cnvrt_project_id: str | None = None,
        collection_id: str | None = None,
        unigraph_project_id: str | None = None,
    ) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT run_id, equipment_tag, runner, status, created_at, started_at,
                           finished_at, agent, request, NULL::jsonb AS result,
                           NULL::jsonb AS trace, error
                    FROM isolation_runs
                    WHERE (%s::text IS NULL OR equipment_tag = %s)
                      AND (%s::text IS NULL OR status = %s)
                      AND (%s::text IS NULL OR request->>'job_id' = %s)
                      AND (%s::text IS NULL OR request->>'cnvrt_project_id' = %s)
                      AND (%s::text IS NULL OR request->>'collection_id' = %s)
                      AND (%s::text IS NULL OR request->>'unigraph_project_id' = %s)
                    ORDER BY created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (
                        equipment_tag, equipment_tag, status, status, job_id, job_id,
                        cnvrt_project_id, cnvrt_project_id, collection_id, collection_id,
                        unigraph_project_id, unigraph_project_id, limit, offset,
                    ),
                )
                rows = cur.fetchall()
        return [_row_to_dict(row) for row in rows]

    def create_plan_from_run(self, run_id: str, area_code: str | None = None) -> tuple[dict, bool]:
        """Atomically promote one succeeded persisted run into advisory plan v1."""
        with self._connection() as conn:
            with conn.cursor() as cur:
                # Locking the source row serializes concurrent promotion requests for
                # the same run without requiring an application-level lock.
                cur.execute(
                    """
                    SELECT run_id, equipment_tag, runner, status, created_at, finished_at,
                           request, agent, result
                    FROM isolation_runs
                    WHERE run_id = %s
                    FOR UPDATE
                    """,
                    (run_id,),
                )
                run = cur.fetchone()
                if not run:
                    raise PlanDomainError("unknown_run", "Unknown persisted run id.", 404)
                if run[3] != "succeeded":
                    raise PlanDomainError(
                        "run_not_succeeded",
                        "Only a succeeded isolation run can be saved as a plan.",
                        409,
                        {"status": run[3]},
                    )
                if run[8] is None:
                    raise PlanDomainError(
                        "result_not_available",
                        "The succeeded run has no persisted result.",
                        409,
                    )
                validate_promotable_result(run[8])

                cur.execute(
                    """
                    SELECT p.plan_id
                    FROM external_run_link l
                    JOIN plan_version v ON v.plan_version_id = l.plan_version_id
                    JOIN isolation_plan p ON p.plan_id = v.plan_id
                    WHERE l.run_id = %s
                    """,
                    (run_id,),
                )
                existing = cur.fetchone()
                if existing:
                    plan = self._get_plan_with_cursor(cur, str(existing[0]))
                    conn.commit()
                    return plan, False

                request_payload = run[6] or {}
                agent_payload = run[7] or {}
                input_hash = canonical_hash(request_payload)
                model_hash = canonical_hash(model_fingerprint(run[2], agent_payload))
                status = derivation_status(agent_payload)
                derived_at = run[5] or run[4]

                cur.execute(
                    """
                    INSERT INTO isolation_plan (plan_number, mode, lifecycle_state, area_code)
                    VALUES (
                        'ISO-' || to_char(now() AT TIME ZONE 'UTC', 'YYYY') || '-' ||
                        lpad(nextval('isolation_plan_number_seq')::text, 6, '0'),
                        'advisory', 'draft', %s
                    )
                    RETURNING plan_id
                    """,
                    (area_code,),
                )
                plan_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO plan_version (
                        plan_id, parent_plan_version_id, version_no, derivation_status,
                        input_hash, model_hash, derived_at
                    )
                    VALUES (%s, NULL, 1, %s, %s, %s, %s)
                    RETURNING plan_version_id
                    """,
                    (plan_id, status, input_hash, model_hash, derived_at),
                )
                version_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO external_run_link (
                        plan_version_id, run_id, runner, link_role, result_uri, trace_uri
                    )
                    VALUES (%s, %s, %s, 'derivation', %s, %s)
                    """,
                    (
                        version_id,
                        run_id,
                        run[2],
                        f"/isolation-runs/{run_id}/result",
                        f"/isolation-runs/{run_id}/trace",
                    ),
                )
                plan = self._get_plan_with_cursor(cur, str(plan_id))
            conn.commit()
        return plan, True

    def get_plan(self, plan_id: str) -> dict | None:
        with self._connection() as conn:
            with conn.cursor() as cur:
                return self._get_plan_with_cursor(cur, plan_id)

    def _get_plan_with_cursor(self, cur, plan_id: str) -> dict | None:
        cur.execute(
            """
            SELECT p.plan_id, p.plan_number, p.active_plan_version_id, p.mode,
                   p.lifecycle_state, p.area_code, p.created_at,
                   v.plan_version_id, v.parent_plan_version_id, v.version_no,
                   v.derivation_status, v.input_hash, v.model_hash, v.derived_at,
                   v.superseded_at, r.run_id, r.runner, r.status, r.equipment_tag,
                   r.created_at, r.request, r.agent,
                   CASE WHEN jsonb_typeof(r.result->'data') = 'array'
                        THEN r.result->'data'->0->>'assurance_status' END
            FROM isolation_plan p
            JOIN plan_version v ON v.plan_id = p.plan_id
            LEFT JOIN external_run_link l
                   ON l.plan_version_id = v.plan_version_id AND l.link_role = 'derivation'
            LEFT JOIN isolation_runs r ON r.run_id = l.run_id
            WHERE p.plan_id = %s
            ORDER BY v.version_no DESC
            """,
            (plan_id,),
        )
        rows = cur.fetchall()
        return _plan_from_rows(rows) if rows else None

    def list_plans(
        self,
        limit: int = 100,
        offset: int = 0,
        lifecycle_state: str | None = None,
        equipment_tag: str | None = None,
        job_id: str | None = None,
        cnvrt_project_id: str | None = None,
        collection_id: str | None = None,
        unigraph_project_id: str | None = None,
        plan_number: str | None = None,
    ) -> tuple[list[dict], int]:
        params = (
            lifecycle_state, lifecycle_state, equipment_tag, equipment_tag,
            job_id, job_id, cnvrt_project_id, cnvrt_project_id,
            collection_id, collection_id, unigraph_project_id, unigraph_project_id,
            plan_number, f"{plan_number}%" if plan_number else None,
        )
        where = """
            WHERE (%s::text IS NULL OR p.lifecycle_state = %s)
              AND (%s::text IS NULL OR r.equipment_tag = %s)
              AND (%s::text IS NULL OR r.request->>'job_id' = %s)
              AND (%s::text IS NULL OR r.request->>'cnvrt_project_id' = %s)
              AND (%s::text IS NULL OR r.request->>'collection_id' = %s)
              AND (%s::text IS NULL OR r.request->>'unigraph_project_id' = %s)
              AND (%s::text IS NULL OR p.plan_number ILIKE %s)
        """
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM isolation_plan p "
                    "JOIN LATERAL (SELECT * FROM plan_version WHERE plan_id = p.plan_id ORDER BY version_no DESC LIMIT 1) v ON true "
                    "LEFT JOIN external_run_link l ON l.plan_version_id = v.plan_version_id AND l.link_role = 'derivation' "
                    "LEFT JOIN isolation_runs r ON r.run_id = l.run_id " + where,
                    params,
                )
                total = int(cur.fetchone()[0])
                cur.execute(
                    """
                    SELECT p.plan_id, p.plan_number, p.active_plan_version_id, p.mode,
                           p.lifecycle_state, p.area_code, p.created_at,
                           v.plan_version_id, v.parent_plan_version_id, v.version_no,
                           v.derivation_status, v.input_hash, v.model_hash, v.derived_at,
                           v.superseded_at, r.run_id, r.runner, r.status, r.equipment_tag,
                           r.created_at, r.request, r.agent,
                           CASE WHEN jsonb_typeof(r.result->'data') = 'array'
                                THEN r.result->'data'->0->>'assurance_status' END
                    FROM isolation_plan p
                    JOIN LATERAL (
                        SELECT * FROM plan_version
                        WHERE plan_id = p.plan_id
                        ORDER BY version_no DESC LIMIT 1
                    ) v ON true
                    LEFT JOIN external_run_link l
                           ON l.plan_version_id = v.plan_version_id AND l.link_role = 'derivation'
                    LEFT JOIN isolation_runs r ON r.run_id = l.run_id
                    """ + where + " ORDER BY p.created_at DESC, p.plan_id DESC LIMIT %s OFFSET %s",
                    (*params, limit, offset),
                )
                rows = cur.fetchall()
        return [_plan_from_rows([row], summary=True) for row in rows], total

    def list_events(self, run_id: str, after_id: int = 0) -> list[dict]:
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event
                    FROM isolation_run_events
                    WHERE run_id = %s AND id > %s
                    ORDER BY id
                    """,
                    (run_id, after_id),
                )
                rows = cur.fetchall()
        return [{"id": row[0], "event": row[1]} for row in rows]


def _plan_from_rows(rows: list[tuple], summary: bool = False) -> dict:
    first = rows[0]
    versions = []
    for row in rows:
        request = row[20] or {}
        run_id = str(row[15]) if row[15] is not None else ""
        source_run = {
            "run_id": run_id,
            "runner": str(row[16] or ""),
            "status": str(row[17] or ""),
            "equipment_tag": str(row[18] or ""),
            "created_at": row[19],
            "assurance_status": row[22],
            "job_id": str(request.get("job_id") or ""),
            "job_name": str(request.get("job_name") or ""),
            "cnvrt_project_id": str(request.get("cnvrt_project_id") or ""),
            "collection_id": str(request.get("collection_id") or ""),
            "unigraph_project_id": str(request.get("unigraph_project_id") or ""),
            "request": {} if summary else request,
            "agent": None if summary else row[21],
            "result_url": f"/isolation-runs/{run_id}/result" if run_id else "",
            "trace_url": f"/isolation-runs/{run_id}/trace" if run_id else "",
        }
        versions.append(
            {
                "plan_version_id": str(row[7]),
                "parent_plan_version_id": str(row[8]) if row[8] else None,
                "version_no": row[9],
                "derivation_status": row[10],
                "input_hash": row[11],
                "model_hash": row[12],
                "derived_at": row[13],
                "superseded_at": row[14],
                "source_run": source_run,
            }
        )
    payload = {
        "plan_id": str(first[0]),
        "plan_number": first[1],
        "active_plan_version_id": str(first[2]) if first[2] else None,
        "mode": first[3],
        "lifecycle_state": first[4],
        "area_code": first[5],
        "created_at": first[6],
        "latest_plan_version_id": versions[0]["plan_version_id"],
        "latest_version": versions[0],
    }
    if not summary:
        payload["versions"] = versions
    return payload


def _record_params(record, request_payload: dict | None = None) -> dict:
    return {
        "run_id": record.run_id,
        "equipment_tag": record.equipment_tag,
        "runner": record.runner,
        "status": record.status,
        "created_at": _dt(record.created_at),
        "started_at": _dt(record.started_at),
        "finished_at": _dt(record.finished_at),
        "request": _json(request_payload or {}),
        "agent": _json(record.agent),
        "result": _json(record.result),
        "trace": _json(record.trace),
        "error": _json(record.error),
    }


def _json(value: Any) -> str:
    return json.dumps(jsonable(value), default=str)


def _dt(value: float | None):
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _ts(value) -> float | None:
    if value is None:
        return None
    return value.timestamp()


def _row_to_dict(row) -> dict:
    return {
        "run_id": row[0],
        "equipment_tag": row[1],
        "runner": row[2],
        "status": row[3],
        "created_at": _ts(row[4]),
        "started_at": _ts(row[5]),
        "finished_at": _ts(row[6]),
        "agent": row[7],
        "request": row[8] or {},
        "result": row[9],
        "trace": row[10],
        "error": row[11],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Equipment isolation API database utility.")
    parser.add_argument("command", choices=["init"])
    parser.add_argument("--schema", default="schema.sql")
    args = parser.parse_args(argv)
    if args.command == "init":
        init_schema(postgres_config_from_env(), args.schema)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
