"""SQLAlchemy-backed PostgreSQL repository for API persistence."""
from __future__ import annotations

from datetime import datetime, timezone
from importlib.resources import files
from typing import Any
from uuid import UUID

from agent.session import jsonable
from api.database import (
    PostgresConfig,
    create_database_engine,
    create_session_factory,
    postgres_config_from_env,
    postgres_configured,
)
from api.db_models import (
    ExternalRunLink,
    IsolationPlan,
    IsolationRun,
    IsolationRunEvent,
    PlanVersion,
    isolation_plan_number_seq,
)
from api.plans import (
    PlanDomainError,
    canonical_hash,
    derivation_status,
    model_fingerprint,
    validate_promotable_result,
)
from sqlalchemy import Text, case, cast, func, inspect, literal, select
from sqlalchemy.orm import aliased, load_only


def _migration_config():
    from alembic.config import Config

    migration_package = files("api.migrations")
    config_resource = migration_package.joinpath("alembic.ini")
    if not config_resource.is_file():
        raise RuntimeError("Packaged Alembic configuration is missing")

    config = Config(str(config_resource))
    config.set_main_option("script_location", str(migration_package))
    return config


def _migration_script_directory():
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(_migration_config())


def migration_head_revision() -> str:
    """Return the single migration head packaged with this application."""
    head = _migration_script_directory().get_current_head()
    if head is None:
        raise RuntimeError("No Alembic migration head is configured")
    return head


class PostgresRunRepository:
    def __init__(self, config: PostgresConfig | None = None, *, engine=None):
        self.config = config or postgres_config_from_env()
        self._engine = engine or create_database_engine(self.config)
        self._session_factory = create_session_factory(self._engine)

    def close(self) -> None:
        self._engine.dispose()

    def check_ready(self) -> None:
        """Fail unless the database is reachable and migrated to application head."""
        from alembic.runtime.migration import MigrationContext

        required_tables = {
            "isolation_runs",
            "isolation_run_events",
            "isolation_plan",
            "plan_version",
            "external_run_link",
        }
        with self._engine.connect() as connection:
            inspector = inspect(connection)
            present_tables = set(inspector.get_table_names(schema="public"))
            legacy_run_columns: set[str] = set()
            if "isolation_runs" in present_tables:
                legacy_run_columns = {
                    str(column["name"])
                    for column in inspector.get_columns("isolation_runs", schema="public")
                    if column["name"] in {"artifacts", "run_dir"}
                }
            current_heads = set(MigrationContext.configure(connection).get_current_heads())

        if not required_tables.issubset(present_tables):
            raise RuntimeError(
                "PostgreSQL is reachable but the equipment-isolation schema is incomplete; "
                "run `uv run alembic upgrade head`"
            )
        if legacy_run_columns:
            raise RuntimeError(
                "PostgreSQL still has unsupported legacy local-artifact columns; "
                "do not stamp it as the current baseline"
            )

        expected_heads = set(_migration_script_directory().get_heads())
        if current_heads != expected_heads:
            current_label = ", ".join(sorted(current_heads)) or "unversioned"
            expected_label = ", ".join(sorted(expected_heads)) or "no packaged head"
            raise RuntimeError(
                "PostgreSQL migration revision is "
                f"{current_label}; expected {expected_label}. "
                "Run `uv run alembic upgrade head`, or verify an existing current-schema "
                "database before stamping the baseline."
            )

    def insert_run(self, record, request_payload: dict) -> None:
        with self._session_factory.begin() as session:
            session.add(
                IsolationRun(
                    run_id=record.run_id,
                    equipment_tag=record.equipment_tag,
                    runner=record.runner,
                    status=record.status,
                    created_at=_dt(record.created_at),
                    started_at=_dt(record.started_at),
                    finished_at=_dt(record.finished_at),
                    request=_jsonable(request_payload or {}),
                    agent=_jsonable(record.agent),
                    result=_jsonable(record.result),
                    trace=_jsonable(record.trace),
                    error=_jsonable(record.error),
                )
            )

    def update_run(self, record) -> None:
        with self._session_factory.begin() as session:
            persisted = session.get(IsolationRun, record.run_id)
            if persisted is None:
                return
            persisted.status = record.status
            persisted.started_at = _dt(record.started_at)
            persisted.finished_at = _dt(record.finished_at)
            persisted.agent = _jsonable(record.agent)
            persisted.result = _jsonable(record.result)
            persisted.trace = _jsonable(record.trace)
            persisted.error = _jsonable(record.error)

    def append_event(self, run_id: str, event: dict) -> None:
        with self._session_factory.begin() as session:
            session.add(IsolationRunEvent(run_id=run_id, event=_jsonable(event)))

    def get_run(self, run_id: str) -> dict | None:
        with self._session_factory() as session:
            run = session.get(IsolationRun, run_id)
            return _run_to_dict(run) if run is not None else None

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
        statement = select(IsolationRun).options(
            load_only(
                IsolationRun.run_id,
                IsolationRun.equipment_tag,
                IsolationRun.runner,
                IsolationRun.status,
                IsolationRun.created_at,
                IsolationRun.started_at,
                IsolationRun.finished_at,
                IsolationRun.agent,
                IsolationRun.request,
                IsolationRun.error,
            )
        )
        if equipment_tag is not None:
            statement = statement.where(IsolationRun.equipment_tag == equipment_tag)
        if status is not None:
            statement = statement.where(IsolationRun.status == status)
        json_filters = {
            "job_id": job_id,
            "cnvrt_project_id": cnvrt_project_id,
            "collection_id": collection_id,
            "unigraph_project_id": unigraph_project_id,
        }
        for key, value in json_filters.items():
            if value is not None:
                statement = statement.where(IsolationRun.request[key].astext == value)
        statement = statement.order_by(IsolationRun.created_at.desc()).limit(limit).offset(offset)
        with self._session_factory() as session:
            runs = session.scalars(statement).all()
            return [_run_to_dict(run, include_payloads=False) for run in runs]

    def create_plan_from_run(self, run_id: str, area_code: str | None = None) -> tuple[dict, bool]:
        """Atomically promote one succeeded persisted run into advisory plan v1."""
        with self._session_factory.begin() as session:
            run = session.scalar(
                select(IsolationRun)
                .where(IsolationRun.run_id == run_id)
                .with_for_update()
            )
            if run is None:
                raise PlanDomainError("unknown_run", "Unknown persisted run id.", 404)
            if run.status != "succeeded":
                raise PlanDomainError(
                    "run_not_succeeded",
                    "Only a succeeded isolation run can be saved as a plan.",
                    409,
                    {"status": run.status},
                )
            if run.result is None:
                raise PlanDomainError(
                    "result_not_available",
                    "The succeeded run has no persisted result.",
                    409,
                )
            validate_promotable_result(run.result)

            existing_plan_id = session.scalar(
                select(PlanVersion.plan_id)
                .join(ExternalRunLink)
                .where(ExternalRunLink.run_id == run_id)
            )
            if existing_plan_id is not None:
                plan = self._get_plan_with_session(session, existing_plan_id)
                return plan, False

            request_payload = run.request or {}
            agent_payload = run.agent or {}
            input_hash = canonical_hash(request_payload)
            model_hash = canonical_hash(model_fingerprint(run.runner, agent_payload))
            status = derivation_status(agent_payload)
            derived_at = run.finished_at or run.created_at
            plan_number = session.scalar(_plan_number_statement())

            plan_row = IsolationPlan(
                plan_number=plan_number,
                mode="advisory",
                lifecycle_state="draft",
                area_code=area_code,
            )
            session.add(plan_row)
            session.flush()
            version = PlanVersion(
                plan_id=plan_row.plan_id,
                parent_plan_version_id=None,
                version_no=1,
                derivation_status=status,
                input_hash=input_hash,
                model_hash=model_hash,
                derived_at=derived_at,
            )
            session.add(version)
            session.flush()
            session.add(
                ExternalRunLink(
                    plan_version_id=version.plan_version_id,
                    run_id=run_id,
                    runner=run.runner,
                    link_role="derivation",
                    result_uri=f"/isolation-runs/{run_id}/result",
                    trace_uri=f"/isolation-runs/{run_id}/trace",
                )
            )
            session.flush()
            plan = self._get_plan_with_session(session, plan_row.plan_id)
            return plan, True

    def get_plan(self, plan_id: str) -> dict | None:
        try:
            parsed_plan_id = UUID(plan_id)
        except (TypeError, ValueError):
            return None
        with self._session_factory() as session:
            return self._get_plan_with_session(session, parsed_plan_id)

    def _get_plan_with_session(self, session, plan_id: UUID) -> dict | None:
        assurance_status = _assurance_status_expression(IsolationRun)
        statement = (
            select(*_plan_columns(IsolationPlan, PlanVersion, IsolationRun, assurance_status))
            .select_from(IsolationPlan)
            .join(PlanVersion, PlanVersion.plan_id == IsolationPlan.plan_id)
            .outerjoin(
                ExternalRunLink,
                (ExternalRunLink.plan_version_id == PlanVersion.plan_version_id)
                & (ExternalRunLink.link_role == "derivation"),
            )
            .outerjoin(IsolationRun, IsolationRun.run_id == ExternalRunLink.run_id)
            .where(IsolationPlan.plan_id == plan_id)
            .order_by(PlanVersion.version_no.desc())
        )
        rows = session.execute(statement).all()
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
        ranked_versions = (
            select(
                PlanVersion,
                func.row_number()
                .over(
                    partition_by=PlanVersion.plan_id,
                    order_by=PlanVersion.version_no.desc(),
                )
                .label("version_rank"),
            )
            .subquery()
        )
        latest_version = aliased(PlanVersion, ranked_versions)
        assurance_status = _assurance_status_expression(IsolationRun)
        filters = _plan_filters(
            IsolationPlan,
            IsolationRun,
            lifecycle_state=lifecycle_state,
            equipment_tag=equipment_tag,
            job_id=job_id,
            cnvrt_project_id=cnvrt_project_id,
            collection_id=collection_id,
            unigraph_project_id=unigraph_project_id,
            plan_number=plan_number,
        )
        statement = (
            select(*_plan_columns(IsolationPlan, latest_version, IsolationRun, assurance_status))
            .select_from(IsolationPlan)
            .join(
                latest_version,
                (latest_version.plan_id == IsolationPlan.plan_id)
                & (ranked_versions.c.version_rank == 1),
            )
            .outerjoin(
                ExternalRunLink,
                (ExternalRunLink.plan_version_id == latest_version.plan_version_id)
                & (ExternalRunLink.link_role == "derivation"),
            )
            .outerjoin(IsolationRun, IsolationRun.run_id == ExternalRunLink.run_id)
            .where(*filters)
            .order_by(IsolationPlan.created_at.desc(), IsolationPlan.plan_id.desc())
        )
        paged_statement = statement.limit(limit).offset(offset)
        count_statement = (
            select(func.count())
            .select_from(IsolationPlan)
            .join(
                latest_version,
                (latest_version.plan_id == IsolationPlan.plan_id)
                & (ranked_versions.c.version_rank == 1),
            )
            .outerjoin(
                ExternalRunLink,
                (ExternalRunLink.plan_version_id == latest_version.plan_version_id)
                & (ExternalRunLink.link_role == "derivation"),
            )
            .outerjoin(IsolationRun, IsolationRun.run_id == ExternalRunLink.run_id)
            .where(*filters)
        )
        with self._session_factory() as session:
            total = int(session.scalar(count_statement) or 0)
            rows = session.execute(paged_statement).all()
            return [_plan_from_rows([row], summary=True) for row in rows], total

    def list_events(self, run_id: str, after_id: int = 0) -> list[dict]:
        statement = (
            select(IsolationRunEvent.id, IsolationRunEvent.event)
            .where(
                IsolationRunEvent.run_id == run_id,
                IsolationRunEvent.id > after_id,
            )
            .order_by(IsolationRunEvent.id)
        )
        with self._session_factory() as session:
            rows = session.execute(statement).all()
            return [{"id": row.id, "event": row.event} for row in rows]


def _plan_number_statement():
    return select(
        literal("ISO-")
        + func.to_char(func.timezone("UTC", func.now()), "YYYY")
        + literal("-")
        + func.lpad(cast(isolation_plan_number_seq.next_value(), Text), 6, "0")
    )


def _assurance_status_expression(run_model):
    return case(
        (
            func.jsonb_typeof(run_model.result["data"]) == "array",
            run_model.result["data"][0]["assurance_status"].astext,
        ),
        else_=None,
    ).label("assurance_status")


def _plan_columns(plan_model, version_model, run_model, assurance_status):
    return (
        plan_model.plan_id,
        plan_model.plan_number,
        plan_model.active_plan_version_id,
        plan_model.mode,
        plan_model.lifecycle_state,
        plan_model.area_code,
        plan_model.created_at,
        version_model.plan_version_id,
        version_model.parent_plan_version_id,
        version_model.version_no,
        version_model.derivation_status,
        version_model.input_hash,
        version_model.model_hash,
        version_model.derived_at,
        version_model.superseded_at,
        run_model.run_id,
        run_model.runner,
        run_model.status,
        run_model.equipment_tag,
        run_model.created_at,
        run_model.request,
        run_model.agent,
        assurance_status,
    )


def _plan_filters(plan_model, run_model, **values):
    filters = []
    if values["lifecycle_state"] is not None:
        filters.append(plan_model.lifecycle_state == values["lifecycle_state"])
    if values["equipment_tag"] is not None:
        filters.append(run_model.equipment_tag == values["equipment_tag"])
    for key in ("job_id", "cnvrt_project_id", "collection_id", "unigraph_project_id"):
        if values[key] is not None:
            filters.append(run_model.request[key].astext == values[key])
    if values["plan_number"] is not None:
        filters.append(plan_model.plan_number.ilike(f"{values['plan_number']}%"))
    return filters


def _plan_from_rows(rows: list, summary: bool = False) -> dict:
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


def _jsonable(value: Any):
    return jsonable(value) if value is not None else None


def _dt(value: float | None):
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _ts(value) -> float | None:
    if value is None:
        return None
    return value.timestamp()


def _run_to_dict(run: IsolationRun, *, include_payloads: bool = True) -> dict:
    return {
        "run_id": run.run_id,
        "equipment_tag": run.equipment_tag,
        "runner": run.runner,
        "status": run.status,
        "created_at": _ts(run.created_at),
        "started_at": _ts(run.started_at),
        "finished_at": _ts(run.finished_at),
        "agent": run.agent,
        "request": run.request or {},
        "result": run.result if include_payloads else None,
        "trace": run.trace if include_payloads else None,
        "error": run.error,
    }
