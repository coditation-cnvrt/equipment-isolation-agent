"""SQLAlchemy-backed PostgreSQL repository for API persistence."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib.resources import files
from typing import Any
from uuid import UUID

from sqlalchemy import Text, case, cast, func, inspect, literal, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased, load_only

from equipment_isolation.agent.session import jsonable
from equipment_isolation.api.database import (
    PostgresConfig,
    create_database_engine,
    create_session_factory,
    postgres_config_from_env,
    postgres_configured,
)
from equipment_isolation.api.db_models import (
    AssetCondition,
    AssetConditionEvent,
    AssetReference,
    AuditEvent,
    DerivationManifest,
    DerivationManifestFeedback,
    ExternalRunLink,
    FeedbackApplicationResult,
    FeedbackReviewDecision,
    Finding,
    InputSnapshot,
    IsolationBranch,
    IsolationPlan,
    IsolationRun,
    IsolationRunEvent,
    NormalizedIsolationPoint,
    PathPoint,
    PlanFeedback,
    PlanStep,
    PlanVersion,
    PlanVersionAssetCondition,
    PlanVersionFeedback,
    PlanWorkScope,
    WorkScopeAsset,
    isolation_plan_number_seq,
)
from equipment_isolation.api.plans import (
    PlanDomainError,
    assurance_status,
    canonical_hash,
    derivation_status,
    model_fingerprint,
    normalized_plan_content,
    plan_content_diff,
    validate_promotable_result,
)
from equipment_isolation.domain.feedback import (
    POINT_FEEDBACK_TYPES,
    allowed_point_feedback_types,
    derivation_effect,
    feedback_transition_group,
    point_feedback_state,
    validate_feedback_category,
)


ASSET_EVENT_REPLAY_OVERLAP = timedelta(minutes=10)


def _migration_config():
    from alembic.config import Config

    migration_package = files("equipment_isolation.api.migrations")
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
                    for column in inspector.get_columns(
                        "isolation_runs", schema="public"
                    )
                    if column["name"] in {"artifacts", "run_dir"}
                }
            current_heads = set(
                MigrationContext.configure(connection).get_current_heads()
            )

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

    def create_asset_condition(self, payload, actor_id: str) -> dict:
        context = payload.asset.context()
        try:
            with self._session_factory.begin() as session:
                asset = _get_or_create_asset(
                    session,
                    payload.asset.external_system,
                    payload.asset.external_id,
                    payload.asset.tag,
                    payload.asset.asset_class,
                    context,
                )
                existing = session.scalar(
                    select(AssetCondition)
                    .where(
                        AssetCondition.asset_ref_id == asset.asset_ref_id,
                        AssetCondition.condition_type == payload.condition_type,
                        AssetCondition.state == "active",
                    )
                    .with_for_update()
                )
                if existing is not None:
                    raise PlanDomainError(
                        "asset_condition_already_active",
                        "This asset already has an active unavailable condition.",
                        409,
                        {"condition_id": str(existing.condition_id)},
                    )
                condition = AssetCondition(
                    asset_ref_id=asset.asset_ref_id,
                    condition_type=payload.condition_type,
                    state="active",
                    reason_code=str(payload.reason_code or "").strip() or None,
                    notes=payload.notes,
                    evidence=_jsonable(payload.evidence),
                    source_system=str(payload.source_system or "").strip() or None,
                    source_reference=_jsonable(payload.source_reference),
                    reported_by=actor_id,
                )
                session.add(condition)
                session.flush()
                session.add(
                    AssetConditionEvent(
                        condition_id=condition.condition_id,
                        event_type="reported",
                        actor_id=actor_id,
                        payload=_jsonable(
                            {
                                "reason_code": condition.reason_code,
                                "notes": condition.notes,
                                "evidence": condition.evidence,
                            }
                        ),
                    )
                )
                session.flush()
                return _asset_condition_dict(session, condition)
        except IntegrityError as error:
            raise PlanDomainError(
                "asset_condition_already_active",
                "This asset already has an active unavailable condition.",
                409,
            ) from error

    def get_asset_condition(self, condition_id: str) -> dict | None:
        condition_uuid = _uuid(condition_id, "unknown_asset_condition")
        with self._session_factory() as session:
            condition = session.get(AssetCondition, condition_uuid)
            return _asset_condition_dict(session, condition) if condition else None

    def list_asset_conditions(
        self,
        *,
        cnvrt_project_id: str,
        collection_id: str,
        unigraph_project_id: str,
        job_id: str = "",
        state: str = "active",
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        context = {
            "cnvrt_project_id": str(cnvrt_project_id),
            "collection_id": str(collection_id),
            "unigraph_project_id": str(unigraph_project_id),
            "job_id": str(job_id or ""),
        }
        scope_keys = {_asset_scope_key("unigraph_candidate", context)}
        if context["job_id"]:
            scope_keys.add(_asset_scope_key("cnvrt_drawing_entity", context))
        with self._session_factory() as session:
            filters = [AssetReference.scope_key.in_(scope_keys)]
            if state != "all":
                filters.append(AssetCondition.state == state)
            base = (
                select(AssetCondition)
                .join(AssetReference, AssetReference.asset_ref_id == AssetCondition.asset_ref_id)
                .where(*filters)
            )
            statement = (
                base
                .order_by(AssetCondition.reported_at.desc(), AssetCondition.condition_id)
                .limit(limit)
                .offset(offset)
            )
            total = int(
                session.scalar(
                    select(func.count()).select_from(base.order_by(None).subquery())
                )
                or 0
            )
            items = _asset_condition_dicts(
                session,
                session.scalars(statement).all(),
                include_events=True,
            )
            return items, total

    def confirm_asset_condition(self, condition_id: str, payload, actor_id: str) -> dict:
        condition_uuid = _uuid(condition_id, "unknown_asset_condition")
        with self._session_factory.begin() as session:
            condition = session.scalar(
                select(AssetCondition)
                .where(AssetCondition.condition_id == condition_uuid)
                .with_for_update()
            )
            if condition is None:
                raise PlanDomainError("unknown_asset_condition", "Unknown asset condition.", 404)
            if condition.state != "active":
                raise PlanDomainError(
                    "asset_condition_not_active",
                    "Only an active asset condition can be confirmed.",
                    409,
                )
            if condition.confirmed_at is not None:
                raise PlanDomainError(
                    "asset_condition_already_confirmed",
                    "This asset condition has already been confirmed.",
                    409,
                )
            condition.confirmed_by = actor_id
            condition.confirmed_at = func.now()
            session.add(
                AssetConditionEvent(
                    condition_id=condition.condition_id,
                    event_type="confirmed",
                    actor_id=actor_id,
                    payload=_jsonable({"reason": payload.reason, "evidence": payload.evidence}),
                )
            )
            session.flush()
            return _asset_condition_dict(session, condition)

    def clear_asset_condition(self, condition_id: str, payload, actor_id: str) -> dict:
        condition_uuid = _uuid(condition_id, "unknown_asset_condition")
        with self._session_factory.begin() as session:
            condition = session.scalar(
                select(AssetCondition)
                .where(AssetCondition.condition_id == condition_uuid)
                .with_for_update()
            )
            if condition is None:
                raise PlanDomainError("unknown_asset_condition", "Unknown asset condition.", 404)
            if condition.state != "active":
                raise PlanDomainError(
                    "asset_condition_already_cleared",
                    "This asset condition has already been cleared.",
                    409,
                )
            condition.state = "cleared"
            condition.cleared_by = actor_id
            condition.cleared_at = func.now()
            condition.clear_reason = payload.reason
            session.add(
                AssetConditionEvent(
                    condition_id=condition.condition_id,
                    event_type="cleared",
                    actor_id=actor_id,
                    payload=_jsonable({"reason": payload.reason, "evidence": payload.evidence}),
                )
            )
            session.flush()
            return _asset_condition_dict(session, condition)

    def active_asset_conditions_for_run(self, request_payload: dict) -> list[dict]:
        """Return exact-identity active conditions to snapshot into a new run."""

        context = {
            "cnvrt_project_id": str(request_payload.get("cnvrt_project_id") or ""),
            "collection_id": str(request_payload.get("collection_id") or ""),
            "unigraph_project_id": str(request_payload.get("unigraph_project_id") or ""),
            "job_id": str(request_payload.get("job_id") or ""),
        }
        scope_keys = {_asset_scope_key("unigraph_candidate", context)}
        if context["job_id"]:
            scope_keys.add(_asset_scope_key("cnvrt_drawing_entity", context))
        with self._session_factory() as session:
            conditions = session.scalars(
                select(AssetCondition)
                .join(AssetReference, AssetReference.asset_ref_id == AssetCondition.asset_ref_id)
                .where(
                    AssetCondition.state == "active",
                    AssetReference.scope_key.in_(scope_keys),
                )
                .order_by(AssetCondition.reported_at, AssetCondition.condition_id)
            ).all()
            return _asset_condition_dicts(
                session, conditions, include_events=False
            )

    def latest_asset_condition_event_id(self, context: dict[str, str]) -> str:
        scope_keys = _asset_scope_keys(context)
        with self._session_factory() as session:
            event_id = session.scalar(
                select(AssetConditionEvent.event_id)
                .join(AssetCondition, AssetCondition.condition_id == AssetConditionEvent.condition_id)
                .join(AssetReference, AssetReference.asset_ref_id == AssetCondition.asset_ref_id)
                .where(AssetReference.scope_key.in_(scope_keys))
                .order_by(AssetConditionEvent.occurred_at.desc(), AssetConditionEvent.event_id.desc())
                .limit(1)
            )
            return str(event_id) if event_id else ""

    def asset_condition_event_replay_state(
        self,
        context: dict[str, str],
        after_id: str = "",
    ) -> dict:
        """Establish a replay watermark and IDs already visible around it.

        The overlap allows an event whose transaction commits late to appear
        after a later-timestamped event without being skipped permanently.
        """

        scope_keys = _asset_scope_keys(context)
        with self._session_factory() as session:
            cursor = _scoped_asset_condition_event(
                session, scope_keys, after_id
            ) if after_id else None
            if cursor is None:
                cursor = session.scalar(
                    select(AssetConditionEvent)
                    .join(
                        AssetCondition,
                        AssetCondition.condition_id == AssetConditionEvent.condition_id,
                    )
                    .join(
                        AssetReference,
                        AssetReference.asset_ref_id == AssetCondition.asset_ref_id,
                    )
                    .where(AssetReference.scope_key.in_(scope_keys))
                    .order_by(
                        AssetConditionEvent.occurred_at.desc(),
                        AssetConditionEvent.event_id.desc(),
                    )
                    .limit(1)
                )
            if cursor is None:
                return {"cursor_id": "", "cursor_occurred_at": None, "seen_ids": set()}
            cutoff = cursor.occurred_at - ASSET_EVENT_REPLAY_OVERLAP
            seen_ids = {
                str(event_id)
                for event_id in session.scalars(
                    select(AssetConditionEvent.event_id)
                    .join(
                        AssetCondition,
                        AssetCondition.condition_id == AssetConditionEvent.condition_id,
                    )
                    .join(
                        AssetReference,
                        AssetReference.asset_ref_id == AssetCondition.asset_ref_id,
                    )
                    .where(
                        AssetReference.scope_key.in_(scope_keys),
                        AssetConditionEvent.occurred_at >= cutoff,
                        or_(
                            AssetConditionEvent.occurred_at < cursor.occurred_at,
                            (
                                (AssetConditionEvent.occurred_at == cursor.occurred_at)
                                & (
                                    cast(AssetConditionEvent.event_id, Text)
                                    <= str(cursor.event_id)
                                )
                            ),
                        ),
                    )
                ).all()
            }
            return {
                "cursor_id": str(cursor.event_id),
                "cursor_occurred_at": cursor.occurred_at,
                "seen_ids": seen_ids,
            }

    def list_asset_condition_events(
        self,
        context: dict[str, str],
        *,
        after_id: str = "",
        exclude_ids: set[str] | None = None,
        limit: int = 100,
    ) -> list[dict]:
        scope_keys = _asset_scope_keys(context)
        with self._session_factory() as session:
            cursor = _scoped_asset_condition_event(session, scope_keys, after_id)
            statement = (
                select(AssetConditionEvent, AssetCondition, AssetReference)
                .join(AssetCondition, AssetCondition.condition_id == AssetConditionEvent.condition_id)
                .join(AssetReference, AssetReference.asset_ref_id == AssetCondition.asset_ref_id)
                .where(AssetReference.scope_key.in_(scope_keys))
            )
            if cursor is not None:
                statement = statement.where(
                    AssetConditionEvent.occurred_at
                    >= cursor.occurred_at - ASSET_EVENT_REPLAY_OVERLAP
                )
            parsed_exclusions = []
            for item in exclude_ids or set():
                try:
                    parsed_exclusions.append(UUID(str(item)))
                except (TypeError, ValueError):
                    continue
            if parsed_exclusions:
                statement = statement.where(
                    AssetConditionEvent.event_id.not_in(parsed_exclusions)
                )
            rows = session.execute(
                statement.order_by(
                    AssetConditionEvent.occurred_at,
                    AssetConditionEvent.event_id,
                ).limit(limit)
            ).all()
            return [
                {
                    "event_id": str(event.event_id),
                    "type": "asset_condition.changed",
                    "event_type": event.event_type,
                    "condition_id": str(condition.condition_id),
                    "condition_type": condition.condition_type,
                    "state": condition.state,
                    "occurred_at": event.occurred_at,
                    "asset": _asset_reference_dict(asset),
                    "payload": event.payload or {},
                }
                for event, condition, asset in rows
            ]

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
                    parent_run_id=getattr(record, "parent_run_id", None),
                )
            )
            context = (request_payload or {}).get("derivation_context") or {}
            if context.get("manifest_id"):
                manifest = session.get(
                    DerivationManifest, UUID(str(context["manifest_id"]))
                )
                if manifest is None or manifest.state != "locked":
                    raise PlanDomainError(
                        "invalid_derivation_manifest",
                        "Derivation manifest is not available.",
                        409,
                    )
                manifest.run_id = record.run_id
                manifest.state = "running"

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
            context = (persisted.request or {}).get("derivation_context") or {}
            if context.get("manifest_id"):
                manifest = session.get(
                    DerivationManifest, UUID(str(context["manifest_id"]))
                )
                if manifest is not None and record.status == "failed":
                    manifest.state = "failed"
                    manifest.finished_at = _dt(record.finished_at)
                    manifest.error = _jsonable(record.error)
                elif (
                    manifest is not None
                    and record.status == "succeeded"
                    and manifest.child_plan_version_id is None
                ):
                    self._complete_derivation(session, manifest, persisted)

    def update_run_request(self, run_id: str, request_payload: dict) -> None:
        """Persist context inferred while a run is still executing."""

        with self._session_factory.begin() as session:
            persisted = session.get(IsolationRun, run_id)
            if persisted is not None:
                persisted.request = _jsonable(request_payload or {})

    def append_event(self, run_id: str, event: dict) -> None:
        with self._session_factory.begin() as session:
            session.add(IsolationRunEvent(run_id=run_id, event=_jsonable(event)))

    def get_run(self, run_id: str) -> dict | None:
        with self._session_factory() as session:
            run = session.get(IsolationRun, run_id)
            if run is None:
                return None
            result = _run_to_dict(run)
            manifest = session.scalar(
                select(DerivationManifest)
                .where(DerivationManifest.run_id == run_id)
                .limit(1)
            )
            if manifest is not None:
                result["derivation_manifest_id"] = str(manifest.manifest_id)
                result["produced_plan_version_id"] = (
                    str(manifest.child_plan_version_id)
                    if manifest.child_plan_version_id
                    else None
                )
            return result

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
                IsolationRun.parent_run_id,
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
        statement = (
            statement.order_by(IsolationRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        with self._session_factory() as session:
            runs = session.scalars(statement).all()
            return [_run_to_dict(run, include_payloads=False) for run in runs]

    def create_plan_from_run(
        self, run_id: str, area_code: str | None = None
    ) -> tuple[dict, bool]:
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
                normalization_status="complete",
                assurance_status=assurance_status(run.result),
                content=normalized_plan_content(request_payload, run.result),
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
            _persist_normalized_content(session, version, request_payload, run.result)
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
            select(
                *_plan_columns(
                    IsolationPlan, PlanVersion, IsolationRun, assurance_status
                )
            )
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
        if not rows:
            return None
        payload = _plan_from_rows(rows)
        payload["freshness"] = _plan_freshness(
            session,
            UUID(payload["latest_plan_version_id"]),
            rows[0][22] or {},
        )
        return payload

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
        ranked_versions = select(
            PlanVersion,
            func.row_number()
            .over(
                partition_by=PlanVersion.plan_id,
                order_by=PlanVersion.version_no.desc(),
            )
            .label("version_rank"),
        ).subquery()
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
            select(
                *_plan_columns(
                    IsolationPlan, latest_version, IsolationRun, assurance_status
                )
            )
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
            freshness_by_version = _plans_freshness(
                session,
                [
                    (UUID(str(row[7])), row[22] or {})
                    for row in rows
                ],
            )
            items = []
            for row in rows:
                payload = _plan_from_rows([row], summary=True)
                payload["freshness"] = freshness_by_version[
                    UUID(payload["latest_plan_version_id"])
                ]
                items.append(payload)
            return items, total

    def create_change(self, plan_id: str, payload, actor_id: str) -> dict:
        plan_uuid = _uuid(plan_id, "unknown_plan")
        version_uuid = _uuid(payload.raised_against_version_id, "unknown_plan_version")
        with self._session_factory.begin() as session:
            plan = session.scalar(
                select(IsolationPlan)
                .where(IsolationPlan.plan_id == plan_uuid)
                .with_for_update()
            )
            if plan is None:
                raise PlanDomainError("unknown_plan", "Unknown plan id.", 404)
            latest = session.scalar(
                select(PlanVersion)
                .where(PlanVersion.plan_id == plan_uuid)
                .order_by(PlanVersion.version_no.desc())
                .limit(1)
            )
            if latest is None or latest.plan_version_id != version_uuid:
                raise PlanDomainError(
                    "stale_plan_version",
                    "Corrections may only target the latest plan version.",
                    409,
                )
            if latest.normalization_status != "complete" or not latest.content:
                raise PlanDomainError(
                    "legacy_plan_not_correctable",
                    "This historical plan is not normalized; create a fresh run and plan.",
                    409,
                )
            points = list(latest.content.get("points") or [])
            point_by_key = {str(item.get("key")): item for item in points}
            point_keys = set(point_by_key)
            branch_keys = {
                str(item.get("key")) for item in (latest.content.get("branches") or [])
            }
            if payload.change_type == "add_manual_isolation_point":
                if payload.target_type != "isolation_point":
                    raise PlanDomainError(
                        "invalid_feedback_target_type",
                        "Missing-point feedback must target an isolation point.",
                        422,
                    )
                requested_identities = {
                    str(value).strip()
                    for value in (
                        payload.target_id,
                        payload.proposed_change.get("drawing_entity_id"),
                    )
                    if value not in (None, "")
                }
                existing = next(
                    (
                        item
                        for item in points
                        if requested_identities & _point_identities(item)
                    ),
                    None,
                )
                if existing is not None:
                    raise PlanDomainError(
                        "point_already_present",
                        "This drawing entity is already present in the latest plan version.",
                        409,
                        {"target_id": str(existing.get("key") or payload.target_id)},
                    )
            else:
                if payload.change_type in POINT_FEEDBACK_TYPES and payload.target_type not in {
                    "candidate",
                    "isolation_point",
                }:
                    raise PlanDomainError(
                        "invalid_feedback_target_type",
                        "This correction must target an isolation point.",
                        422,
                    )
                valid = point_keys if payload.target_type in {"candidate", "isolation_point"} else branch_keys
                if payload.target_id not in valid:
                    raise PlanDomainError(
                        "invalid_correction_target",
                        "Correction target is not present in the latest plan version.",
                        422,
                    )
                if payload.change_type in POINT_FEEDBACK_TYPES:
                    point = point_by_key[payload.target_id]
                    allowed = allowed_point_feedback_types(point)
                    if payload.change_type not in allowed:
                        raise PlanDomainError(
                            "invalid_feedback_transition",
                            "That correction is not valid for the point's current state.",
                            409,
                            {
                                "current_state": point_feedback_state(point).value,
                                "allowed_actions": sorted(allowed),
                            },
                        )
                    if payload.change_type == "correct_label":
                        proposed_label = str(payload.proposed_change.get("label") or "").strip()
                        current_label = str(
                            point.get("tag_number")
                            or point.get("tag")
                            or point.get("equipment_id")
                            or ""
                        ).strip()
                        if proposed_label == current_label:
                            raise PlanDomainError(
                                "invalid_feedback_transition",
                                "The corrected equipment tag is unchanged.",
                                409,
                                {
                                    "current_state": point_feedback_state(point).value,
                                    "allowed_actions": sorted(allowed),
                                },
                            )
            category = validate_feedback_category(
                payload.change_type,
                getattr(payload, "feedback_category", None),
            ).value
            transition_group = feedback_transition_group(payload.change_type)
            open_feedback = session.scalars(
                select(PlanFeedback).where(
                    PlanFeedback.plan_id == plan_uuid,
                    PlanFeedback.raised_against_version_id == version_uuid,
                    PlanFeedback.target_id == payload.target_id,
                    PlanFeedback.state.in_(("submitted", "approved")),
                )
            ).all()
            pending = next(
                (
                    item
                    for item in open_feedback
                    if feedback_transition_group(item.feedback_type) == transition_group
                ),
                None,
            )
            if pending is not None:
                raise PlanDomainError(
                    "feedback_transition_pending",
                    "A correction for this aspect of the point is already awaiting derivation.",
                    409,
                    {
                        "pending_feedback_id": str(pending.feedback_id),
                        "pending_feedback_type": pending.feedback_type,
                    },
                )
            supersedes_id = None
            if getattr(payload, "supersedes_feedback_id", None):
                supersedes_id = _uuid(
                    payload.supersedes_feedback_id, "unknown_feedback"
                )
                superseded = session.scalar(
                    select(PlanFeedback).where(
                        PlanFeedback.feedback_id == supersedes_id,
                        PlanFeedback.plan_id == plan_uuid,
                    )
                )
                if superseded is None:
                    raise PlanDomainError(
                        "unknown_feedback",
                        "Superseded feedback does not belong to this plan.",
                        422,
                    )
                if superseded.feedback_category != category:
                    raise PlanDomainError(
                        "feedback_category_mismatch",
                        "Feedback may only supersede feedback in the same category.",
                        422,
                    )
            row = PlanFeedback(
                plan_id=plan_uuid,
                raised_against_version_id=version_uuid,
                feedback_category=category,
                feedback_type=payload.change_type,
                target_type=payload.target_type,
                target_id=payload.target_id,
                proposed_change=_jsonable(payload.proposed_change),
                justification=payload.justification,
                source_system=getattr(payload, "source_system", None),
                source_reference=_jsonable(
                    getattr(payload, "source_reference", {}) or {}
                ),
                evidence=_jsonable(getattr(payload, "evidence", {}) or {}),
                supersedes_feedback_id=supersedes_id,
                state="submitted",
                raised_by=actor_id,
            )
            session.add(row)
            session.flush()
            _append_audit(
                session,
                plan_uuid,
                version_uuid,
                "feedback_submitted",
                actor_id,
                {
                    "feedback_id": str(row.feedback_id),
                    "feedback_category": row.feedback_category,
                    "feedback_type": row.feedback_type,
                    "target_id": row.target_id,
                },
            )
            return _feedback_to_dict(row)

    def approve_change(self, plan_id: str, change_id: str, actor_id: str) -> dict:
        plan_uuid, change_uuid = (
            _uuid(plan_id, "unknown_plan"),
            _uuid(change_id, "unknown_change"),
        )
        with self._session_factory.begin() as session:
            plan = session.scalar(
                select(IsolationPlan)
                .where(IsolationPlan.plan_id == plan_uuid)
                .with_for_update()
            )
            if plan is None:
                raise PlanDomainError("unknown_plan", "Unknown plan id.", 404)
            row = session.scalar(
                select(PlanFeedback)
                .where(
                    PlanFeedback.feedback_id == change_uuid,
                    PlanFeedback.plan_id == plan_uuid,
                )
                .with_for_update()
            )
            if row is None:
                raise PlanDomainError(
                    "unknown_change", "Unknown correction request.", 404
                )
            self_approval = row.raised_by == actor_id
            if self_approval and plan.mode != "advisory":
                raise PlanDomainError(
                    "self_approval_forbidden",
                    "A correction must be approved by a different authenticated user.",
                    409,
                )
            if row.state == "approved":
                return _feedback_to_dict(
                    row, _review_decisions(session, row.feedback_id)
                )
            if row.state != "submitted":
                raise PlanDomainError(
                    "invalid_change_state",
                    "Only submitted corrections can be approved.",
                    409,
                    {"state": row.state},
                )
            row.state, row.approved_by, row.approved_at = (
                "approved",
                actor_id,
                func.now(),
            )
            session.flush()
            session.add(
                FeedbackReviewDecision(
                    feedback_id=row.feedback_id,
                    decision="approved",
                    actor_id=actor_id,
                )
            )
            if row.supersedes_feedback_id is not None:
                superseded = session.get(PlanFeedback, row.supersedes_feedback_id)
                if superseded is not None and superseded.state in {
                    "submitted",
                    "approved",
                    "applied",
                }:
                    superseded.state = "superseded"
            session.flush()
            _append_audit(
                session,
                plan_uuid,
                row.raised_against_version_id,
                "feedback_approved",
                actor_id,
                {
                    "feedback_id": str(row.feedback_id),
                    "self_approval": self_approval,
                    "plan_mode": plan.mode,
                },
            )
            return _feedback_to_dict(row, _review_decisions(session, row.feedback_id))

    def list_changes(self, plan_id: str) -> list[dict]:
        plan_uuid = _uuid(plan_id, "unknown_plan")
        with self._session_factory() as session:
            rows = session.scalars(
                select(PlanFeedback)
                .where(PlanFeedback.plan_id == plan_uuid)
                .order_by(PlanFeedback.created_at.desc())
            ).all()
            if not rows and session.get(IsolationPlan, plan_uuid) is None:
                raise PlanDomainError("unknown_plan", "Unknown plan id.", 404)
            result = []
            for row in rows:
                item = _feedback_to_dict(
                    row, _review_decisions(session, row.feedback_id)
                )
                application = session.scalar(
                    select(PlanVersionFeedback)
                    .where(PlanVersionFeedback.feedback_id == row.feedback_id)
                    .order_by(PlanVersionFeedback.applied_at.desc())
                    .limit(1)
                )
                coverage = session.scalar(
                    select(FeedbackApplicationResult)
                    .where(FeedbackApplicationResult.feedback_id == row.feedback_id)
                    .order_by(FeedbackApplicationResult.validated_at.desc())
                    .limit(1)
                )
                if application:
                    item["application_outcome"] = application.application_outcome
                if coverage:
                    item.update(
                        coverage_status=coverage.status, coverage_reason=coverage.reason
                    )
                result.append(item)
            return result

    def prepare_derivation(
        self,
        plan_id: str,
        parent_version_id: str,
        actor_id: str,
        trigger: str = "corrections",
    ) -> dict:
        plan_uuid, parent_uuid = (
            _uuid(plan_id, "unknown_plan"),
            _uuid(parent_version_id, "unknown_plan_version"),
        )
        with self._session_factory.begin() as session:
            plan = session.scalar(
                select(IsolationPlan)
                .where(IsolationPlan.plan_id == plan_uuid)
                .with_for_update()
            )
            if plan is None:
                raise PlanDomainError("unknown_plan", "Unknown plan id.", 404)
            parent = session.scalar(
                select(PlanVersion)
                .where(PlanVersion.plan_id == plan_uuid)
                .order_by(PlanVersion.version_no.desc())
                .limit(1)
            )
            if parent is None or parent.plan_version_id != parent_uuid:
                raise PlanDomainError(
                    "stale_plan_version",
                    "Derivation parent is not the latest plan version.",
                    409,
                )
            if parent.normalization_status != "complete":
                raise PlanDomainError(
                    "legacy_plan_not_correctable",
                    "This historical plan is not normalized.",
                    409,
                )
            active = session.scalar(
                select(DerivationManifest)
                .where(
                    DerivationManifest.plan_id == plan_uuid,
                    DerivationManifest.state.in_(("locked", "running")),
                )
                .limit(1)
            )
            if active:
                raise PlanDomainError(
                    "derivation_in_progress",
                    "A correction derivation is already running for this plan.",
                    409,
                )
            changes = session.scalars(
                select(PlanFeedback)
                .where(
                    PlanFeedback.plan_id == plan_uuid, PlanFeedback.state == "approved"
                )
                .order_by(PlanFeedback.created_at)
            ).all()
            effective_changes = session.scalars(
                select(PlanFeedback)
                .where(
                    PlanFeedback.plan_id == plan_uuid,
                    PlanFeedback.state.in_(("applied", "approved")),
                )
                .order_by(PlanFeedback.created_at, PlanFeedback.feedback_id)
            ).all()
            source_run = session.scalar(
                select(IsolationRun)
                .join(ExternalRunLink, ExternalRunLink.run_id == IsolationRun.run_id)
                .where(
                    ExternalRunLink.plan_version_id == parent_uuid,
                    ExternalRunLink.link_role == "derivation",
                )
            )
            if source_run is None:
                raise PlanDomainError(
                    "source_run_missing",
                    "Parent plan version has no derivation run.",
                    409,
                )
            freshness = _plan_freshness(
                session, parent.plan_version_id, source_run.request or {}
            )
            conditions_stale = freshness["status"] == "stale"
            if trigger == "corrections" and not changes:
                raise PlanDomainError(
                    "no_approved_corrections",
                    "No approved corrections are available for derivation.",
                    409,
                )
            if trigger == "asset_conditions" and not conditions_stale:
                raise PlanDomainError(
                    "plan_inputs_current",
                    "The latest plan version already uses the current shared equipment status.",
                    409,
                )
            corrections = [
                _feedback_to_derivation_input(item) for item in effective_changes
            ]
            trigger_kind = (
                "combined"
                if conditions_stale and changes
                else "asset_conditions"
                if conditions_stale
                else "corrections"
            )
            trigger_snapshot = {
                "requested_trigger": trigger,
                "effective_trigger": trigger_kind,
                "freshness": freshness,
            }
            manifest = DerivationManifest(
                plan_id=plan_uuid,
                parent_plan_version_id=parent_uuid,
                state="locked",
                trigger_kind=trigger_kind,
                trigger_snapshot=_jsonable(trigger_snapshot),
                policy_hash=canonical_hash(
                    {"corrections": corrections, "trigger": trigger_snapshot}
                ),
                created_by=actor_id,
            )
            session.add(manifest)
            session.flush()
            for change in changes:
                session.add(
                    DerivationManifestFeedback(
                        manifest_id=manifest.manifest_id,
                        feedback_id=change.feedback_id,
                        mandatory=True,
                        required_effects={
                            "feedback_category": change.feedback_category,
                            "feedback_type": change.feedback_type,
                            "effect": derivation_effect(change.feedback_type).value,
                        },
                    )
                )
            request_payload = dict(source_run.request or {})
            request_payload.pop("derivation_context", None)
            request_payload["approved_corrections"] = corrections
            request_payload["derivation_context"] = {
                "manifest_id": str(manifest.manifest_id),
                "plan_id": plan_id,
                "parent_plan_version_id": parent_version_id,
                "trigger_kind": trigger_kind,
            }
            _append_audit(
                session,
                plan_uuid,
                parent_uuid,
                "derivation_locked",
                actor_id,
                {
                    "manifest_id": str(manifest.manifest_id),
                    "trigger_kind": trigger_kind,
                    "feedback_ids": [str(row.feedback_id) for row in changes],
                    "asset_condition_changes": freshness["changes"],
                },
            )
            return {
                "manifest_id": str(manifest.manifest_id),
                "parent_run_id": source_run.run_id,
                "request": request_payload,
            }

    def fail_derivation_launch(
        self, manifest_id: str, actor_id: str, error: dict
    ) -> None:
        manifest_uuid = _uuid(manifest_id, "unknown_derivation_manifest")
        with self._session_factory.begin() as session:
            manifest = session.scalar(
                select(DerivationManifest)
                .where(DerivationManifest.manifest_id == manifest_uuid)
                .with_for_update()
            )
            if manifest is None or manifest.state not in {"locked", "running"}:
                return
            manifest.state = "failed"
            manifest.finished_at = func.now()
            manifest.error = _jsonable(error)
            _append_audit(
                session,
                manifest.plan_id,
                manifest.parent_plan_version_id,
                "derivation_launch_failed",
                actor_id,
                {"manifest_id": str(manifest.manifest_id), "error": error},
            )

    def get_plan_version(self, plan_id: str, version_id: str) -> dict | None:
        plan_uuid, version_uuid = (
            _uuid(plan_id, "unknown_plan"),
            _uuid(version_id, "unknown_plan_version"),
        )
        with self._session_factory() as session:
            row = session.scalar(
                select(PlanVersion).where(
                    PlanVersion.plan_id == plan_uuid,
                    PlanVersion.plan_version_id == version_uuid,
                )
            )
            if row is None:
                return None
            return {
                "plan_version_id": str(row.plan_version_id),
                "plan_id": str(row.plan_id),
                "parent_plan_version_id": str(row.parent_plan_version_id)
                if row.parent_plan_version_id
                else None,
                "version_no": row.version_no,
                "normalization_status": row.normalization_status,
                "assurance_status": row.assurance_status,
                "content": row.content or {},
            }

    def get_plan_version_diff(self, plan_id: str, version_id: str) -> dict | None:
        plan_uuid, version_uuid = (
            _uuid(plan_id, "unknown_plan"),
            _uuid(version_id, "unknown_plan_version"),
        )
        with self._session_factory() as session:
            row = session.scalar(
                select(PlanVersion).where(
                    PlanVersion.plan_id == plan_uuid,
                    PlanVersion.plan_version_id == version_uuid,
                )
            )
            if row is None:
                return None
            parent = (
                session.get(PlanVersion, row.parent_plan_version_id)
                if row.parent_plan_version_id
                else None
            )
            diff = plan_content_diff(
                parent.content if parent else None, row.content or {}
            )
            return {
                "plan_id": plan_id,
                "from_version_id": str(parent.plan_version_id) if parent else None,
                "to_version_id": version_id,
                **diff,
            }

    def _complete_derivation(
        self, session, manifest: DerivationManifest, run: IsolationRun
    ) -> None:
        parent = session.scalar(
            select(PlanVersion)
            .where(PlanVersion.plan_version_id == manifest.parent_plan_version_id)
            .with_for_update()
        )
        plan = session.scalar(
            select(IsolationPlan)
            .where(IsolationPlan.plan_id == manifest.plan_id)
            .with_for_update()
        )
        if parent is None or plan is None:
            raise RuntimeError("Derivation parent disappeared")
        latest_no = int(
            session.scalar(
                select(func.max(PlanVersion.version_no)).where(
                    PlanVersion.plan_id == plan.plan_id
                )
            )
            or 0
        )
        if latest_no != parent.version_no:
            raise RuntimeError("Derivation completed against a stale parent")
        content = normalized_plan_content(run.request or {}, run.result or {})
        coverage_by_id = {
            str(item.get("change_id")): item
            for item in (content.get("correction_coverage") or [])
        }
        manifest_changes = session.scalars(
            select(DerivationManifestFeedback).where(
                DerivationManifestFeedback.manifest_id == manifest.manifest_id
            )
        ).all()
        degraded = False
        version = PlanVersion(
            plan_id=plan.plan_id,
            parent_plan_version_id=parent.plan_version_id,
            version_no=parent.version_no + 1,
            derivation_status=derivation_status(run.agent),
            input_hash=canonical_hash(run.request or {}),
            model_hash=canonical_hash(model_fingerprint(run.runner, run.agent)),
            derived_at=run.finished_at or run.created_at,
            normalization_status="complete",
            assurance_status=assurance_status(run.result),
            content=content,
        )
        session.add(version)
        session.flush()
        session.add(
            ExternalRunLink(
                plan_version_id=version.plan_version_id,
                run_id=run.run_id,
                runner=run.runner,
                link_role="derivation",
                result_uri=f"/isolation-runs/{run.run_id}/result",
                trace_uri=f"/isolation-runs/{run.run_id}/trace",
            )
        )
        _persist_normalized_content(
            session, version, run.request or {}, run.result or {}
        )
        for link in manifest_changes:
            change = session.get(PlanFeedback, link.feedback_id)
            coverage = coverage_by_id.get(str(link.feedback_id)) or {
                "status": "failed",
                "reason": "Pipeline returned no feedback application result.",
            }
            status, reason = (
                str(coverage.get("status") or "failed"),
                str(coverage.get("reason") or ""),
            )
            degraded = degraded or status != "applied"
            session.add(
                FeedbackApplicationResult(
                    manifest_id=manifest.manifest_id,
                    feedback_id=link.feedback_id,
                    status=status,
                    reason=reason,
                    evidence=_jsonable(coverage),
                )
            )
            session.add(
                PlanVersionFeedback(
                    plan_version_id=version.plan_version_id,
                    feedback_id=link.feedback_id,
                    application_outcome=status,
                    derivation_note=reason,
                )
            )
            if change is not None and status == "applied":
                change.state = "applied"
        if degraded:
            version.derivation_status = "completed_degraded"
        parent.superseded_at = func.now()
        for stale in session.scalars(
            select(PlanFeedback).where(
                PlanFeedback.plan_id == plan.plan_id,
                PlanFeedback.state == "submitted",
                PlanFeedback.raised_against_version_id == parent.plan_version_id,
            )
        ).all():
            stale.state = "superseded"
        manifest.state, manifest.child_plan_version_id, manifest.finished_at = (
            "completed",
            version.plan_version_id,
            func.now(),
        )
        _append_audit(
            session,
            plan.plan_id,
            version.plan_version_id,
            "plan_version_derived",
            "system",
            {
                "manifest_id": str(manifest.manifest_id),
                "trigger_kind": manifest.trigger_kind,
                "run_id": run.run_id,
                "parent_plan_version_id": str(parent.plan_version_id),
            },
        )

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
        version_model.normalization_status,
        version_model.assurance_status,
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
        request = row[22] or {}
        run_id = str(row[17]) if row[17] is not None else ""
        source_run = {
            "run_id": run_id,
            "runner": str(row[18] or ""),
            "status": str(row[19] or ""),
            "equipment_tag": str(row[20] or ""),
            "created_at": row[21],
            "assurance_status": row[24] or row[16],
            "job_id": str(request.get("job_id") or ""),
            "job_name": str(request.get("job_name") or ""),
            "cnvrt_project_id": str(request.get("cnvrt_project_id") or ""),
            "collection_id": str(request.get("collection_id") or ""),
            "unigraph_project_id": str(request.get("unigraph_project_id") or ""),
            "request": {} if summary else request,
            "agent": None if summary else row[23],
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
                "normalization_status": row[15],
                "assurance_status": row[16],
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


def _plan_freshness(session, version_id: UUID, request: dict) -> dict:
    return _plans_freshness(session, [(version_id, request)])[version_id]


def _plans_freshness(
    session,
    version_requests: list[tuple[UUID, dict]],
) -> dict[UUID, dict]:
    """Compute freshness for a plan page with a fixed number of SQL queries."""

    evaluated_at = datetime.now(timezone.utc)
    if not version_requests:
        return {}
    contexts = {
        version_id: {
            "cnvrt_project_id": str((request or {}).get("cnvrt_project_id") or ""),
            "collection_id": str((request or {}).get("collection_id") or ""),
            "unigraph_project_id": str((request or {}).get("unigraph_project_id") or ""),
            "job_id": str((request or {}).get("job_id") or ""),
        }
        for version_id, request in version_requests
    }
    valid_contexts = {
        version_id: context
        for version_id, context in contexts.items()
        if all(
            context[key]
            for key in ("cnvrt_project_id", "collection_id", "unigraph_project_id")
        )
    }
    version_ids = set(valid_contexts)
    captured_rows = session.execute(
        select(
            PlanVersionAssetCondition.plan_version_id,
            PlanVersionAssetCondition.condition_id,
            PlanVersionAssetCondition.snapshot,
        ).where(PlanVersionAssetCondition.plan_version_id.in_(version_ids))
    ).all()
    captured_by_version: dict[UUID, dict[str, dict]] = {
        version_id: {} for version_id in version_ids
    }
    for row in captured_rows:
        captured_by_version[row.plan_version_id][str(row.condition_id)] = row.snapshot or {}

    scope_keys = set().union(
        *(_asset_scope_keys(context) for context in valid_contexts.values())
    ) if valid_contexts else set()
    current_rows = session.execute(
        select(AssetCondition, AssetReference)
        .join(AssetReference, AssetReference.asset_ref_id == AssetCondition.asset_ref_id)
        .where(
            AssetCondition.state == "active",
            AssetReference.scope_key.in_(scope_keys),
        )
        .order_by(AssetCondition.reported_at, AssetCondition.condition_id)
    ).all()
    current_by_scope: dict[str, dict[str, dict]] = {}
    for condition, asset in current_rows:
        current_by_scope.setdefault(asset.scope_key, {})[str(condition.condition_id)] = (
            _asset_condition_dict(
                session,
                condition,
                include_events=False,
                asset=asset,
            )
        )

    current_by_version: dict[UUID, dict[str, dict]] = {}
    removed_ids: set[str] = set()
    for version_id, context in valid_contexts.items():
        current: dict[str, dict] = {}
        for scope_key in _asset_scope_keys(context):
            current.update(current_by_scope.get(scope_key, {}))
        current_by_version[version_id] = current
        removed_ids.update(
            set(captured_by_version[version_id]) - set(current)
        )
    removed_conditions = {
        str(condition.condition_id): condition
        for condition in (
            session.scalars(
                select(AssetCondition).where(
                    AssetCondition.condition_id.in_([UUID(item) for item in removed_ids])
                )
            ).all()
            if removed_ids
            else []
        )
    }

    results: dict[UUID, dict] = {}
    for version_id, _request in version_requests:
        if version_id not in valid_contexts:
            results[version_id] = {
                "status": "unknown",
                "reason": None,
                "evaluated_at": evaluated_at,
                "changes": [],
            }
            continue
        captured = captured_by_version[version_id]
        current = current_by_version[version_id]
        changes = []
        for condition_id in sorted(set(current) - set(captured)):
            item = current[condition_id]
            changes.append(
                {
                    "change_type": "became_unavailable",
                    "condition_id": condition_id,
                    "occurred_at": item["reported_at"],
                    "asset": item["asset"],
                }
            )
        for condition_id in sorted(set(captured) - set(current)):
            condition = removed_conditions.get(condition_id)
            changes.append(
                {
                    "change_type": "returned_to_service",
                    "condition_id": condition_id,
                    "occurred_at": (
                        condition.cleared_at
                        if condition is not None and condition.cleared_at is not None
                        else evaluated_at
                    ),
                    "asset": (captured[condition_id] or {}).get("asset") or {},
                }
            )
        changes.sort(key=lambda item: (item["occurred_at"], item["condition_id"]))
        results[version_id] = {
            "status": "stale" if changes else "fresh",
            "reason": "asset_condition_changed" if changes else None,
            "evaluated_at": evaluated_at,
            "changes": changes,
        }
    return results


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
        "parent_run_id": run.parent_run_id,
        "derivation_manifest_id": str(
            ((run.request or {}).get("derivation_context") or {}).get("manifest_id")
            or ""
        )
        or None,
    }


def _persist_normalized_content(
    session, version: PlanVersion, request: dict, result: dict
) -> None:
    content = version.content or normalized_plan_content(request, result)
    scope = PlanWorkScope(
        plan_version_id=version.plan_version_id,
        payload=_jsonable(content.get("work_scope") or {}),
    )
    session.add(scope)
    session.flush()
    selected = content.get("selected_asset") or content.get("target_identity") or {}
    selected_external = str(
        selected.get("hilt_entity_id")
        or selected.get("unigraph_vertex_id")
        or request.get("equipment_tag")
        or ""
    )
    if selected_external:
        selected_system = (
            "selected_asset_hilt"
            if selected.get("hilt_entity_id")
            else "selected_asset_unigraph"
            if selected.get("unigraph_vertex_id")
            else "selected_equipment_tag"
        )
        asset = _get_or_create_asset(
            session,
            selected_system,
            selected_external,
            str(
                selected.get("tag") or request.get("equipment_tag") or selected_external
            ),
            str(selected.get("entity_class") or ""),
            content.get("context") or {},
        )
        session.add(
            WorkScopeAsset(
                work_scope_id=scope.work_scope_id,
                asset_ref_id=asset.asset_ref_id,
                scope_role="primary",
                selection_source=str(selected.get("selection_source") or "run_request"),
            )
        )
    session.add(
        InputSnapshot(
            plan_version_id=version.plan_version_id,
            source_type="run_request",
            content_hash=canonical_hash(request),
            payload=_jsonable(request),
        )
    )
    asset_conditions = list((request or {}).get("asset_conditions") or [])
    if asset_conditions:
        session.add(
            InputSnapshot(
                plan_version_id=version.plan_version_id,
                source_type="shared_asset_conditions",
                content_hash=canonical_hash(asset_conditions),
                payload=_jsonable({"items": asset_conditions}),
            )
        )
        for snapshot in asset_conditions:
            try:
                condition_id = UUID(str(snapshot.get("condition_id") or ""))
            except (TypeError, ValueError):
                continue
            if session.get(AssetCondition, condition_id) is None:
                continue
            session.add(
                PlanVersionAssetCondition(
                    plan_version_id=version.plan_version_id,
                    condition_id=condition_id,
                    snapshot=_jsonable(snapshot),
                )
            )
    session.add(
        InputSnapshot(
            plan_version_id=version.plan_version_id,
            source_type="derived_plan_projection",
            content_hash=canonical_hash(content),
            payload=_jsonable(
                {
                    "schema_version": content.get("schema_version"),
                    "target_identity": content.get("target_identity"),
                }
            ),
        )
    )

    branch_rows = {}
    for item in content.get("branches") or []:
        row = IsolationBranch(
            plan_version_id=version.plan_version_id,
            branch_key=str(item["key"]),
            topology_signature=str(
                item.get("topology_signature") or canonical_hash(item)
            ),
            payload=_jsonable(item),
        )
        session.add(row)
        session.flush()
        branch_rows[str(item["key"])] = row
    for item in content.get("points") or []:
        drawing_id = str(item.get("drawing_entity_id") or "").strip()
        external_id = drawing_id or str(item.get("external_id") or item["key"])
        external_system = "cnvrt_drawing_entity" if drawing_id else "unigraph_candidate"
        asset = _get_or_create_asset(
            session,
            external_system,
            external_id,
            str(item.get("tag") or external_id),
            str(item.get("asset_class") or ""),
            content.get("context") or {},
        )
        point = NormalizedIsolationPoint(
            plan_version_id=version.plan_version_id,
            asset_ref_id=asset.asset_ref_id,
            point_key=str(item["key"]),
            provenance=str(item.get("provenance") or "derived"),
            payload=_jsonable(item),
        )
        session.add(point)
        session.flush()
        for membership in item.get("branch_memberships") or [
            {"branch_key": item.get("branch_key") or "unassigned", "path_order": 0}
        ]:
            branch = branch_rows.get(str(membership.get("branch_key") or "unassigned"))
            if branch:
                session.add(
                    PathPoint(
                        branch_id=branch.branch_id,
                        isolation_point_id=point.isolation_point_id,
                        path_order=int(membership.get("path_order") or 0),
                    )
                )
    for index, item in enumerate(content.get("steps") or [], 1):
        session.add(
            PlanStep(
                plan_version_id=version.plan_version_id,
                step_key=str(item["key"]),
                sequence_no=int(item.get("sequence_no") or index),
                payload=_jsonable(item),
            )
        )
    for item in content.get("findings") or []:
        session.add(
            Finding(
                plan_version_id=version.plan_version_id,
                finding_key=str(item["key"]),
                blocks_authorisation=bool(item.get("blocks_authorisation")),
                payload=_jsonable(item),
            )
        )


def _get_or_create_asset(
    session, system: str, external_id: str, tag: str, asset_class: str, context: dict
):
    scope_key = _asset_scope_key(system, context)
    row = session.scalar(
        select(AssetReference).where(
            AssetReference.external_system == system,
            AssetReference.scope_key == scope_key,
            AssetReference.external_id == external_id,
        )
    )
    if row is None:
        row = AssetReference(
            external_system=system,
            scope_key=scope_key,
            external_id=external_id,
            tag=tag,
            asset_class=asset_class,
            context=_jsonable(context or {}),
        )
        session.add(row)
        session.flush()
    return row


def _asset_scope_key(system: str, context: dict) -> str:
    context = context or {}
    if "unigraph" in system:
        project_id = str(
            context.get("unigraph_project_id") or context.get("project_id") or ""
        ).strip()
        if project_id:
            return f"unigraph:{project_id}"
    if "hilt" in system or "drawing" in system:
        return "cnvrt:{project}:collection:{collection}:job:{job}".format(
            project=str(context.get("cnvrt_project_id") or "unknown"),
            collection=str(context.get("collection_id") or "unknown"),
            job=str(context.get("job_id") or "unknown"),
        )
    return "context:" + canonical_hash(context)


def _asset_scope_keys(context: dict) -> set[str]:
    normalized = {
        "cnvrt_project_id": str((context or {}).get("cnvrt_project_id") or ""),
        "collection_id": str((context or {}).get("collection_id") or ""),
        "unigraph_project_id": str((context or {}).get("unigraph_project_id") or ""),
        "job_id": str((context or {}).get("job_id") or ""),
    }
    keys = {_asset_scope_key("unigraph_candidate", normalized)}
    if normalized["job_id"]:
        keys.add(_asset_scope_key("cnvrt_drawing_entity", normalized))
    return keys


def _scoped_asset_condition_event(session, scope_keys: set[str], event_id: str):
    if not event_id:
        return None
    try:
        event_uuid = UUID(str(event_id))
    except (TypeError, ValueError):
        return None
    return session.scalar(
        select(AssetConditionEvent)
        .join(
            AssetCondition,
            AssetCondition.condition_id == AssetConditionEvent.condition_id,
        )
        .join(
            AssetReference,
            AssetReference.asset_ref_id == AssetCondition.asset_ref_id,
        )
        .where(
            AssetConditionEvent.event_id == event_uuid,
            AssetReference.scope_key.in_(scope_keys),
        )
    )


def _asset_reference_dict(asset: AssetReference) -> dict:
    return {
        "asset_ref_id": str(asset.asset_ref_id),
        "external_system": asset.external_system,
        "scope_key": asset.scope_key,
        "external_id": asset.external_id,
        "tag": asset.tag,
        "asset_class": asset.asset_class,
        "context": asset.context or {},
    }


def _asset_condition_dict(
    session,
    condition: AssetCondition,
    *,
    include_events: bool = True,
    asset: AssetReference | None = None,
    events: list[AssetConditionEvent] | None = None,
) -> dict:
    asset = asset or session.get(AssetReference, condition.asset_ref_id)
    event_rows = events or []
    if include_events:
        if events is None:
            event_rows = session.scalars(
                select(AssetConditionEvent)
                .where(AssetConditionEvent.condition_id == condition.condition_id)
                .order_by(AssetConditionEvent.occurred_at, AssetConditionEvent.event_id)
            ).all()
        serialized_events = [
            {
                "event_id": str(item.event_id),
                "event_type": item.event_type,
                "actor_id": item.actor_id,
                "occurred_at": item.occurred_at,
                "payload": item.payload or {},
            }
            for item in event_rows
        ]
    else:
        serialized_events = []
    return {
        "condition_id": str(condition.condition_id),
        "condition_type": condition.condition_type,
        "state": condition.state,
        "reason_code": condition.reason_code,
        "notes": condition.notes,
        "evidence": condition.evidence or {},
        "source_system": condition.source_system,
        "source_reference": condition.source_reference or {},
        "reported_by": condition.reported_by,
        "reported_at": condition.reported_at,
        "confirmed_by": condition.confirmed_by,
        "confirmed_at": condition.confirmed_at,
        "cleared_by": condition.cleared_by,
        "cleared_at": condition.cleared_at,
        "clear_reason": condition.clear_reason,
        "asset": _asset_reference_dict(asset),
        "events": serialized_events,
    }


def _asset_condition_dicts(
    session,
    conditions: list[AssetCondition],
    *,
    include_events: bool,
) -> list[dict]:
    """Serialize a condition page with two bounded relationship queries."""

    if not conditions:
        return []
    asset_ids = {item.asset_ref_id for item in conditions}
    assets = {
        item.asset_ref_id: item
        for item in session.scalars(
            select(AssetReference).where(AssetReference.asset_ref_id.in_(asset_ids))
        ).all()
    }
    events_by_condition: dict[UUID, list[AssetConditionEvent]] = {
        item.condition_id: [] for item in conditions
    }
    if include_events:
        condition_ids = set(events_by_condition)
        event_rows = session.scalars(
            select(AssetConditionEvent)
            .where(AssetConditionEvent.condition_id.in_(condition_ids))
            .order_by(
                AssetConditionEvent.condition_id,
                AssetConditionEvent.occurred_at,
                AssetConditionEvent.event_id,
            )
        ).all()
        for event in event_rows:
            events_by_condition[event.condition_id].append(event)
    return [
        _asset_condition_dict(
            session,
            condition,
            include_events=include_events,
            asset=assets[condition.asset_ref_id],
            events=(events_by_condition[condition.condition_id] if include_events else None),
        )
        for condition in conditions
    ]


def _append_audit(
    session, plan_id, version_id, event_type: str, actor_id: str, payload: dict
) -> None:
    previous = session.scalar(
        select(AuditEvent.event_hash)
        .where(AuditEvent.plan_id == plan_id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.audit_event_id.desc())
        .limit(1)
    )
    occurred_at = datetime.now(timezone.utc)
    event_hash = canonical_hash(
        {
            "previous_hash": previous,
            "plan_id": str(plan_id),
            "plan_version_id": str(version_id) if version_id else None,
            "event_type": event_type,
            "actor_id": actor_id,
            "occurred_at": occurred_at.isoformat(),
            "payload": payload,
        }
    )
    session.add(
        AuditEvent(
            plan_id=plan_id,
            plan_version_id=version_id,
            event_type=event_type,
            actor_id=actor_id,
            occurred_at=occurred_at,
            payload=_jsonable(payload),
            previous_hash=previous,
            event_hash=event_hash,
        )
    )


def _point_identities(point: dict) -> set[str]:
    return {
        str(value).strip()
        for value in (
            point.get("key"),
            point.get("external_id"),
            point.get("uuid"),
            point.get("candidate_id"),
            point.get("drawing_entity_id"),
            point.get("visual_id"),
            point.get("source_visual_id"),
        )
        if value not in (None, "")
    }


def _feedback_to_dict(row: PlanFeedback, review_decisions=()) -> dict:
    """Return the compatibility correction contract plus typed feedback fields."""
    return {
        "change_id": str(row.feedback_id),
        "plan_id": str(row.plan_id),
        "raised_against_version_id": str(row.raised_against_version_id),
        "change_type": row.feedback_type,
        "feedback_category": row.feedback_category,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "proposed_change": row.proposed_change or {},
        "justification": row.justification,
        "source_system": row.source_system,
        "source_reference": row.source_reference or {},
        "evidence": row.evidence or {},
        "supersedes_feedback_id": (
            str(row.supersedes_feedback_id) if row.supersedes_feedback_id else None
        ),
        "state": row.state,
        "raised_by": row.raised_by,
        "approved_by": row.approved_by,
        "created_at": row.created_at,
        "approved_at": row.approved_at,
        "review_decisions": [
            _review_decision_to_dict(item) for item in review_decisions
        ],
    }


def _feedback_to_derivation_input(row: PlanFeedback) -> dict:
    effect = derivation_effect(row.feedback_type)
    return {
        "change_id": str(row.feedback_id),
        "feedback_category": row.feedback_category,
        "feedback_effect": effect.value,
        "change_type": row.feedback_type,
        "target_type": row.target_type,
        "target_id": row.target_id,
        "proposed_change": row.proposed_change or {},
        "justification": row.justification,
        "source_system": row.source_system,
        "source_reference": row.source_reference or {},
        "evidence": row.evidence or {},
        "raised_by": row.raised_by,
        "approved_by": row.approved_by,
    }


def _review_decisions(session, feedback_id: UUID):
    return session.scalars(
        select(FeedbackReviewDecision)
        .where(FeedbackReviewDecision.feedback_id == feedback_id)
        .order_by(
            FeedbackReviewDecision.created_at, FeedbackReviewDecision.review_decision_id
        )
    ).all()


def _review_decision_to_dict(row: FeedbackReviewDecision) -> dict:
    return {
        "review_decision_id": str(row.review_decision_id),
        "decision": row.decision,
        "actor_id": row.actor_id,
        "reason": row.reason,
        "created_at": row.created_at,
    }


def _uuid(value: str, kind: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        raise PlanDomainError(kind, "Identifier is not a valid UUID.", 404) from None
