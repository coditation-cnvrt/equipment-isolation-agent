"""SQLAlchemy ORM mappings for the equipment-isolation PostgreSQL schema."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Sequence,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


isolation_plan_number_seq = Sequence("isolation_plan_number_seq", metadata=Base.metadata)


class IsolationRun(Base):
    __tablename__ = "isolation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="isolation_runs_status_check",
        ),
    )

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    equipment_tag: Mapped[str] = mapped_column(Text, nullable=False)
    runner: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    agent: Mapped[Any | None] = mapped_column(JSONB)
    result: Mapped[Any | None] = mapped_column(JSONB)
    trace: Mapped[Any | None] = mapped_column(JSONB)
    error: Mapped[Any | None] = mapped_column(JSONB)
    parent_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("isolation_runs.run_id", name="isolation_runs_parent_run_id_fkey", ondelete="RESTRICT")
    )

    events: Mapped[list["IsolationRunEvent"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", passive_deletes=True
    )
    external_link: Mapped["ExternalRunLink | None"] = relationship(back_populates="run")


class IsolationRunEvent(Base):
    __tablename__ = "isolation_run_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey(
            "isolation_runs.run_id",
            name="isolation_run_events_run_id_fkey",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    event: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    run: Mapped[IsolationRun] = relationship(back_populates="events")


class IsolationPlan(Base):
    __tablename__ = "isolation_plan"
    __table_args__ = (
        UniqueConstraint("plan_number", name="isolation_plan_plan_number_key"),
        CheckConstraint("mode IN ('advisory')", name="isolation_plan_mode_check"),
        CheckConstraint(
            "lifecycle_state IN ('draft')", name="isolation_plan_lifecycle_state_check"
        ),
        ForeignKeyConstraint(
            ["plan_id", "active_plan_version_id"],
            ["plan_version.plan_id", "plan_version.plan_version_id"],
            name="isolation_plan_active_version_fk",
            ondelete="RESTRICT",
            use_alter=True,
        ),
    )

    plan_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    plan_number: Mapped[str] = mapped_column(Text, nullable=False)
    active_plan_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    mode: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="advisory"
    )
    lifecycle_state: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="draft"
    )
    area_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    versions: Mapped[list["PlanVersion"]] = relationship(
        back_populates="plan",
        primaryjoin="IsolationPlan.plan_id == PlanVersion.plan_id",
        foreign_keys="PlanVersion.plan_id",
        order_by="PlanVersion.version_no",
    )
    active_version: Mapped["PlanVersion | None"] = relationship(
        primaryjoin=(
            "and_(IsolationPlan.plan_id == PlanVersion.plan_id, "
            "IsolationPlan.active_plan_version_id == PlanVersion.plan_version_id)"
        ),
        foreign_keys="[IsolationPlan.plan_id, IsolationPlan.active_plan_version_id]",
        viewonly=True,
    )


class PlanVersion(Base):
    __tablename__ = "plan_version"
    __table_args__ = (
        CheckConstraint("version_no > 0", name="plan_version_version_no_check"),
        CheckConstraint(
            "derivation_status IN ('completed', 'completed_degraded')",
            name="plan_version_derivation_status_check",
        ),
        UniqueConstraint(
            "plan_id", "version_no", name="plan_version_plan_id_version_no_key"
        ),
        UniqueConstraint(
            "plan_id",
            "plan_version_id",
            name="plan_version_plan_id_plan_version_id_key",
        ),
        ForeignKeyConstraint(
            ["plan_id", "parent_plan_version_id"],
            ["plan_version.plan_id", "plan_version.plan_version_id"],
            name="plan_version_plan_id_parent_plan_version_id_fkey",
            ondelete="RESTRICT",
        ),
    )

    plan_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "isolation_plan.plan_id",
            name="plan_version_plan_id_fkey",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    parent_plan_version_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    derivation_status: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    model_hash: Mapped[str] = mapped_column(Text, nullable=False)
    derived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    normalization_status: Mapped[str] = mapped_column(Text, nullable=False, server_default="legacy_incomplete")
    assurance_status: Mapped[str | None] = mapped_column(Text)
    content: Mapped[Any | None] = mapped_column(JSONB)

    plan: Mapped[IsolationPlan] = relationship(
        back_populates="versions",
        primaryjoin="PlanVersion.plan_id == IsolationPlan.plan_id",
        foreign_keys=[plan_id],
        overlaps="active_version",
    )
    parent_version: Mapped["PlanVersion | None"] = relationship(
        remote_side=[plan_id, plan_version_id],
        foreign_keys=[plan_id, parent_plan_version_id],
        uselist=False,
        overlaps="plan,versions",
    )
    run_links: Mapped[list["ExternalRunLink"]] = relationship(back_populates="plan_version")


class ExternalRunLink(Base):
    __tablename__ = "external_run_link"
    __table_args__ = (
        UniqueConstraint("run_id", name="external_run_link_run_id_key"),
        CheckConstraint(
            "link_role IN ('derivation', 'validation', 'comparison')",
            name="external_run_link_link_role_check",
        ),
    )

    run_link_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    plan_version_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "plan_version.plan_version_id",
            name="external_run_link_plan_version_id_fkey",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey(
            "isolation_runs.run_id",
            name="external_run_link_run_id_fkey",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    runner: Mapped[str] = mapped_column(Text, nullable=False)
    link_role: Mapped[str] = mapped_column(Text, nullable=False)
    result_uri: Mapped[str] = mapped_column(Text, nullable=False)
    trace_uri: Mapped[str] = mapped_column(Text, nullable=False)

    plan_version: Mapped[PlanVersion] = relationship(back_populates="run_links")
    run: Mapped[IsolationRun] = relationship(back_populates="external_link")


class AssetReference(Base):
    __tablename__ = "asset_reference"
    __table_args__ = (UniqueConstraint("external_system", "scope_key", "external_id", name="asset_reference_scoped_external_key"),)
    asset_ref_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    external_system: Mapped[str] = mapped_column(Text, nullable=False)
    scope_key: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    tag: Mapped[str] = mapped_column(Text, nullable=False)
    asset_class: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")


class AssetCondition(Base):
    """Current lifecycle record for a shared operational fact about an asset."""

    __tablename__ = "asset_condition"
    __table_args__ = (
        CheckConstraint(
            "condition_type IN ('unavailable')",
            name="asset_condition_type_check",
        ),
        CheckConstraint(
            "state IN ('active','cleared')",
            name="asset_condition_state_check",
        ),
    )
    condition_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    asset_ref_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_reference.asset_ref_id", ondelete="RESTRICT"), nullable=False
    )
    condition_type: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    reason_code: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    source_system: Mapped[str | None] = mapped_column(Text)
    source_reference: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    reported_by: Mapped[str] = mapped_column(Text, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confirmed_by: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cleared_by: Mapped[str | None] = mapped_column(Text)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clear_reason: Mapped[str | None] = mapped_column(Text)


class AssetConditionEvent(Base):
    """Append-only audit history for an asset condition lifecycle."""

    __tablename__ = "asset_condition_event"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('reported','confirmed','cleared')",
            name="asset_condition_event_type_check",
        ),
    )
    event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    condition_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_condition.condition_id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")


class SourceDataDefect(Base):
    __tablename__ = "source_data_defect"
    __table_args__ = (
        CheckConstraint("state IN ('reported','confirmed','remediation_recorded','resolved','rejected','withdrawn')", name="source_data_defect_state_check"),
        CheckConstraint("anchor_type IN ('entity','link','point','region')", name="source_data_defect_anchor_type_check"),
        CheckConstraint("category IN ('missing_device','extra_device','incorrect_device_type','incorrect_symbol','incorrect_label','incorrect_attribute','missing_connection','phantom_connection','incorrect_connection','off_page_connector_mismatch','source_revision_mismatch','other')", name="source_data_defect_category_check"),
        CheckConstraint("length(btrim(anchor_id)) > 0", name="source_data_defect_anchor_id_not_blank_check"),
        CheckConstraint("length(btrim(description)) >= 3", name="source_data_defect_description_check"),
        CheckConstraint("(claimed_by IS NULL) = (claimed_at IS NULL)", name="source_data_defect_claim_consistency_check"),
        CheckConstraint("version > 0", name="source_data_defect_version_check"),
    )
    defect_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    cnvrt_project_id: Mapped[str] = mapped_column(Text, nullable=False)
    collection_id: Mapped[str] = mapped_column(Text, nullable=False)
    unigraph_project_id: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[str] = mapped_column(Text, nullable=False)
    reported_source_revision: Mapped[str | None] = mapped_column(Text)
    reported_source_snapshot_hash: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_type: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_id: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_facts: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="reported")
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    policy_hash: Mapped[str] = mapped_column(Text, nullable=False)
    reported_by: Mapped[str] = mapped_column(Text, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    claimed_by: Mapped[str | None] = mapped_column(Text)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceDataDefectEvent(Base):
    __tablename__ = "source_data_defect_event"
    __table_args__ = (
        UniqueConstraint("defect_id", "defect_version", name="source_data_defect_event_version_key"),
        UniqueConstraint("defect_id", "event_id", name="source_data_defect_event_defect_event_key"),
        CheckConstraint("event_type IN ('reported','confirmed','remediation_recorded','resolved','rejected','withdrawn','reopened','reclassified','commented','evidence_added','claimed','released')", name="source_data_defect_event_type_check"),
        CheckConstraint("to_state IN ('reported','confirmed','remediation_recorded','resolved','rejected','withdrawn')", name="source_data_defect_event_to_state_check"),
        CheckConstraint("from_state IS NULL OR from_state IN ('reported','confirmed','remediation_recorded','resolved','rejected','withdrawn')", name="source_data_defect_event_from_state_check"),
        CheckConstraint("defect_version > 0", name="source_data_defect_event_version_check"),
    )
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    defect_id: Mapped[UUID] = mapped_column(ForeignKey("source_data_defect.defect_id", ondelete="RESTRICT"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    from_state: Mapped[str | None] = mapped_column(Text)
    to_state: Mapped[str] = mapped_column(Text, nullable=False)
    defect_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    previous_hash: Mapped[str | None] = mapped_column(Text)
    event_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


class PlanSourceDependency(Base):
    __table_args__ = (
        CheckConstraint("manifest_status IN ('complete','incomplete','historical_unknown')", name="plan_source_dependency_status_check"),
    )
    __tablename__ = "plan_source_dependency"
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), primary_key=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    manifest_status: Mapped[str] = mapped_column(Text, nullable=False)
    verified_source_revision: Mapped[str | None] = mapped_column(Text)
    verified_source_snapshot_hash: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    exact_anchor_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    source_defect_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    source_defect_snapshots: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    source_defect_event_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, server_default="[]")
    source_defect_event_watermark_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_data_defect_event.event_id", ondelete="RESTRICT"))
    source_defect_event_watermark_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class SourceDefectPlanImpact(Base):
    __tablename__ = "source_defect_plan_impact"
    __table_args__ = (
        UniqueConstraint("event_id", "plan_version_id", name="source_defect_plan_impact_event_version_key"),
        CheckConstraint("match_scope IN ('exact','drawing','drawing_fallback','source_revision')", name="source_defect_plan_impact_scope_check"),
        ForeignKeyConstraint(
            ["defect_id", "event_id"],
            ["source_data_defect_event.defect_id", "source_data_defect_event.event_id"],
            name="source_defect_plan_impact_defect_event_fkey",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["plan_id", "plan_version_id"],
            ["plan_version.plan_id", "plan_version.plan_version_id"],
            name="source_defect_plan_impact_plan_version_fkey",
            ondelete="RESTRICT",
        ),
    )
    impact_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    defect_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    plan_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    match_scope: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlanWorkScope(Base):
    __tablename__ = "work_scope"
    work_scope_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkScopeAsset(Base):
    __tablename__ = "work_scope_asset"
    work_scope_id: Mapped[UUID] = mapped_column(ForeignKey("work_scope.work_scope_id", ondelete="CASCADE"), primary_key=True)
    asset_ref_id: Mapped[UUID] = mapped_column(ForeignKey("asset_reference.asset_ref_id", ondelete="RESTRICT"), primary_key=True)
    scope_role: Mapped[str] = mapped_column(Text, nullable=False)
    selection_source: Mapped[str] = mapped_column(Text, nullable=False)


class InputSnapshot(Base):
    __tablename__ = "input_snapshot"
    snapshot_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class PlanVersionAssetCondition(Base):
    """Immutable record of a shared condition considered by a plan version."""

    __tablename__ = "plan_version_asset_condition"
    plan_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), primary_key=True
    )
    condition_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_condition.condition_id", ondelete="RESTRICT"), primary_key=True
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class IsolationBranch(Base):
    __tablename__ = "isolation_branch"
    __table_args__ = (UniqueConstraint("plan_version_id", "branch_key", name="isolation_branch_version_key"),)
    branch_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False)
    branch_key: Mapped[str] = mapped_column(Text, nullable=False)
    topology_signature: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class NormalizedIsolationPoint(Base):
    __tablename__ = "isolation_point"
    __table_args__ = (UniqueConstraint("plan_version_id", "point_key", name="isolation_point_version_key"),)
    isolation_point_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False)
    asset_ref_id: Mapped[UUID] = mapped_column(ForeignKey("asset_reference.asset_ref_id", ondelete="RESTRICT"), nullable=False)
    point_key: Mapped[str] = mapped_column(Text, nullable=False)
    provenance: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class PathPoint(Base):
    __tablename__ = "path_point"
    branch_id: Mapped[UUID] = mapped_column(ForeignKey("isolation_branch.branch_id", ondelete="CASCADE"), primary_key=True)
    isolation_point_id: Mapped[UUID] = mapped_column(ForeignKey("isolation_point.isolation_point_id", ondelete="CASCADE"), primary_key=True)
    path_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class PlanStep(Base):
    __tablename__ = "plan_step"
    __table_args__ = (UniqueConstraint("plan_version_id", "step_key", name="plan_step_version_key"),)
    step_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False)
    step_key: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Finding(Base):
    __tablename__ = "finding"
    __table_args__ = (UniqueConstraint("plan_version_id", "finding_key", name="finding_version_key"),)
    finding_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False)
    finding_key: Mapped[str] = mapped_column(Text, nullable=False)
    blocks_authorisation: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class PlanFeedback(Base):
    __tablename__ = "plan_feedback"
    __table_args__ = (
        CheckConstraint("state IN ('submitted','approved','rejected','applied','superseded')", name="plan_feedback_state_check"),
        CheckConstraint(
            "feedback_category IN ('input_correction','requirement_deviation','manual_observation','execution_failure')",
            name="plan_feedback_category_check",
        ),
    )
    feedback_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("isolation_plan.plan_id", ondelete="CASCADE"), nullable=False)
    raised_against_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"), nullable=False)
    feedback_category: Mapped[str] = mapped_column(Text, nullable=False)
    feedback_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_change: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    source_system: Mapped[str | None] = mapped_column(Text)
    source_reference: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    supersedes_feedback_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("plan_feedback.feedback_id", ondelete="RESTRICT")
    )
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="submitted")
    raised_by: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FeedbackReviewDecision(Base):
    __tablename__ = "feedback_review_decision"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('approved','rejected')",
            name="feedback_review_decision_value_check",
        ),
    )
    review_decision_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    feedback_id: Mapped[UUID] = mapped_column(
        ForeignKey("plan_feedback.feedback_id", ondelete="RESTRICT"), nullable=False
    )
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DerivationManifest(Base):
    __tablename__ = "derivation_manifest"
    __table_args__ = (
        CheckConstraint("state IN ('locked','running','completed','failed')", name="derivation_manifest_state_check"),
        CheckConstraint(
            "trigger_kind IN ('corrections','asset_conditions','source_data_defects','combined')",
            name="derivation_manifest_trigger_kind_check",
        ),
    )
    manifest_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("isolation_plan.plan_id", ondelete="CASCADE"), nullable=False)
    parent_plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"), nullable=False)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("isolation_runs.run_id", ondelete="RESTRICT"), unique=True)
    child_plan_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"), unique=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="corrections")
    trigger_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    policy_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[Any | None] = mapped_column(JSONB)


class DerivationManifestFeedback(Base):
    __tablename__ = "derivation_manifest_feedback"
    manifest_id: Mapped[UUID] = mapped_column(ForeignKey("derivation_manifest.manifest_id", ondelete="CASCADE"), primary_key=True)
    feedback_id: Mapped[UUID] = mapped_column(ForeignKey("plan_feedback.feedback_id", ondelete="RESTRICT"), primary_key=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    required_effects: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")


class DerivationManifestSourceDataDefect(Base):
    __tablename__ = "derivation_manifest_source_data_defect"
    __table_args__ = (
        ForeignKeyConstraint(
            ["defect_id", "event_id"],
            ["source_data_defect_event.defect_id", "source_data_defect_event.event_id"],
            name="derivation_manifest_source_defect_event_fkey",
            ondelete="RESTRICT",
        ),
    )
    manifest_id: Mapped[UUID] = mapped_column(ForeignKey("derivation_manifest.manifest_id", ondelete="CASCADE"), primary_key=True)
    defect_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class PlanVersionFeedback(Base):
    __tablename__ = "plan_version_feedback"
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), primary_key=True)
    feedback_id: Mapped[UUID] = mapped_column(ForeignKey("plan_feedback.feedback_id", ondelete="RESTRICT"), primary_key=True)
    application_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    derivation_note: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FeedbackApplicationResult(Base):
    __tablename__ = "feedback_application_result"
    __table_args__ = (UniqueConstraint("manifest_id", "feedback_id", name="feedback_application_manifest_feedback_key"),)
    application_result_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    manifest_id: Mapped[UUID] = mapped_column(ForeignKey("derivation_manifest.manifest_id", ondelete="CASCADE"), nullable=False)
    feedback_id: Mapped[UUID] = mapped_column(ForeignKey("plan_feedback.feedback_id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_event"
    audit_event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("isolation_plan.plan_id", ondelete="CASCADE"), nullable=False)
    plan_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(Text)
    event_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)


Index(
    "isolation_runs_status_idx",
    IsolationRun.status,
    IsolationRun.created_at.desc(),
)
Index(
    "isolation_runs_equipment_idx",
    IsolationRun.equipment_tag,
    IsolationRun.created_at.desc(),
)
Index("isolation_runs_parent_run_idx", IsolationRun.parent_run_id, IsolationRun.created_at.desc())
Index("plan_feedback_plan_state_idx", PlanFeedback.plan_id, PlanFeedback.state, PlanFeedback.created_at.desc())
Index(
    "plan_feedback_category_state_idx",
    PlanFeedback.plan_id,
    PlanFeedback.feedback_category,
    PlanFeedback.state,
    PlanFeedback.created_at.desc(),
)
Index(
    "feedback_review_decision_feedback_idx",
    FeedbackReviewDecision.feedback_id,
    FeedbackReviewDecision.created_at.desc(),
)
Index(
    "asset_condition_one_active_type_idx",
    AssetCondition.asset_ref_id,
    AssetCondition.condition_type,
    unique=True,
    postgresql_where=AssetCondition.state == "active",
)
Index(
    "asset_condition_state_reported_idx",
    AssetCondition.state,
    AssetCondition.reported_at.desc(),
)
Index(
    "asset_condition_event_condition_idx",
    AssetConditionEvent.condition_id,
    AssetConditionEvent.occurred_at,
)
Index("source_data_defect_scope_state_idx", SourceDataDefect.cnvrt_project_id, SourceDataDefect.collection_id, SourceDataDefect.job_id, SourceDataDefect.state)
Index("source_data_defect_event_scope_idx", SourceDataDefectEvent.defect_id, SourceDataDefectEvent.occurred_at)
Index("source_defect_plan_impact_event_idx", SourceDefectPlanImpact.event_id, SourceDefectPlanImpact.plan_version_id)
Index("derivation_manifest_plan_state_idx", DerivationManifest.plan_id, DerivationManifest.state)
Index(
    "isolation_run_events_run_id_id_idx",
    IsolationRunEvent.run_id,
    IsolationRunEvent.id,
)
Index(
    "external_run_link_one_derivation_idx",
    ExternalRunLink.plan_version_id,
    unique=True,
    postgresql_where=ExternalRunLink.link_role == "derivation",
)
Index(
    "isolation_plan_created_at_idx",
    IsolationPlan.created_at.desc(),
    IsolationPlan.plan_id.desc(),
)
Index(
    "isolation_plan_state_created_idx",
    IsolationPlan.lifecycle_state,
    IsolationPlan.created_at.desc(),
    IsolationPlan.plan_id.desc(),
)
Index(
    "plan_version_plan_version_no_idx",
    PlanVersion.plan_id,
    PlanVersion.version_no.desc(),
)
Index(
    "isolation_runs_planning_context_idx",
    IsolationRun.equipment_tag,
    IsolationRun.request["cnvrt_project_id"].astext,
    IsolationRun.request["collection_id"].astext,
    IsolationRun.request["job_id"].astext,
    IsolationRun.request["unigraph_project_id"].astext,
)


class ControlledInput(Base):
    __tablename__ = "controlled_input"
    __table_args__ = (
        UniqueConstraint("input_type", "cnvrt_project_id", "collection_id", "job_id", name="controlled_input_scope_key"),
        CheckConstraint("input_type IN ('fhr','sic')", name="controlled_input_type_check"),
        CheckConstraint("length(btrim(cnvrt_project_id)) > 0 AND length(btrim(collection_id)) > 0 AND length(btrim(document_key)) > 0 AND length(btrim(created_by)) > 0", name="controlled_input_identity_check"),
        CheckConstraint("(input_type = 'fhr' AND length(btrim(job_id)) > 0) OR (input_type = 'sic' AND job_id = '')", name="controlled_input_scope_check"),
        ForeignKeyConstraint(["input_id", "approved_revision_id"], ["controlled_input_revision.input_id", "controlled_input_revision.revision_id"], name="controlled_input_head_fk", ondelete="RESTRICT", use_alter=True),
    )
    input_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    input_type: Mapped[str] = mapped_column(Text, nullable=False)
    cnvrt_project_id: Mapped[str] = mapped_column(Text, nullable=False)
    collection_id: Mapped[str] = mapped_column(Text, nullable=False)
    job_id: Mapped[str] = mapped_column(Text, nullable=False)
    document_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    approved_revision_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))


class ControlledInputRevision(Base):
    __tablename__ = "controlled_input_revision"
    __table_args__ = (
        UniqueConstraint("input_id", "revision_label", name="controlled_revision_label_key"),
        UniqueConstraint("input_id", "revision_id", name="controlled_revision_parent_key"),
        CheckConstraint("decision IN ('pending','approved','rejected')", name="controlled_revision_decision_check"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="controlled_revision_hash_check"),
        CheckConstraint("length(btrim(revision_label)) > 0 AND length(btrim(schema_version)) > 0 AND length(btrim(submitted_by)) > 0", name="controlled_revision_identity_check"),
        CheckConstraint("canonical_version = 'controlled-json-v1'", name="controlled_revision_canonical_check"),
        CheckConstraint("(decision = 'pending' AND decided_by IS NULL AND decided_at IS NULL AND decision_reason IS NULL) OR (decision <> 'pending' AND decided_by IS NOT NULL AND decision_reason IS NOT NULL AND length(btrim(decided_by)) > 0 AND decided_at IS NOT NULL AND length(btrim(decision_reason)) > 0)", name="controlled_revision_metadata_check"),
    )
    revision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    input_id: Mapped[UUID] = mapped_column(ForeignKey("controlled_input.input_id", ondelete="RESTRICT"), nullable=False)
    revision_label: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_version: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    validation: Mapped[dict] = mapped_column(JSONB, nullable=False)
    submitted_by: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decision: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    decided_by: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_reason: Mapped[str | None] = mapped_column(Text)


class RunInputManifest(Base):
    __tablename__ = "run_input_manifest"
    __table_args__ = (
        UniqueConstraint("run_id", name="run_input_manifest_run_key"),
        CheckConstraint("mode = 'foundation' AND completeness = 'incomplete'", name="run_input_manifest_foundation_check"),
        CheckConstraint("jsonb_typeof(missing_sources) = 'array' AND jsonb_array_length(missing_sources) > 0", name="run_input_manifest_missing_check"),
        CheckConstraint("schema_version = 'run-input-manifest-v1' AND canonical_version = 'controlled-json-v1'", name="run_input_manifest_schema_check"),
        CheckConstraint("request_hash ~ '^[0-9a-f]{64}$' AND manifest_hash ~ '^[0-9a-f]{64}$'", name="run_input_manifest_hash_check"),
    )
    manifest_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    run_id: Mapped[str] = mapped_column(ForeignKey("isolation_runs.run_id", ondelete="RESTRICT"), nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    semantic_request: Mapped[dict] = mapped_column(JSONB, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_version: Mapped[str] = mapped_column(Text, nullable=False)
    plan_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completeness: Mapped[str] = mapped_column(Text, nullable=False)
    missing_sources: Mapped[list] = mapped_column(JSONB, nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunInputManifestItem(Base):
    __tablename__ = "run_input_manifest_item"
    __table_args__ = (
        ForeignKeyConstraint(["input_id", "revision_id"], ["controlled_input_revision.input_id", "controlled_input_revision.revision_id"], name="run_input_item_revision_fk", ondelete="RESTRICT"),
        CheckConstraint("input_type IN ('fhr','sic') AND role = 'source'", name="run_input_item_slot_check"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="run_input_item_hash_check"),
        Index("run_input_item_revision_idx", "input_id", "revision_id"),
    )
    manifest_id: Mapped[UUID] = mapped_column(ForeignKey("run_input_manifest.manifest_id", ondelete="RESTRICT"), primary_key=True)
    input_type: Mapped[str] = mapped_column(Text, primary_key=True)
    role: Mapped[str] = mapped_column(Text, primary_key=True)
    input_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    approval_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)


class PlanVersionInvalidation(Base):
    __tablename__ = "plan_version_invalidation"
    __table_args__ = (
        ForeignKeyConstraint(["input_id", "consumed_revision_id"], ["controlled_input_revision.input_id", "controlled_input_revision.revision_id"], name="plan_invalidation_consumed_fk", ondelete="RESTRICT"),
        ForeignKeyConstraint(["input_id", "replacement_revision_id"], ["controlled_input_revision.input_id", "controlled_input_revision.revision_id"], name="plan_invalidation_replacement_fk", ondelete="RESTRICT"),
        CheckConstraint("consumed_revision_id <> replacement_revision_id AND reason = 'approved_revision_replaced'", name="plan_invalidation_reason_check"),
    )
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"), primary_key=True)
    consumed_revision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    replacement_revision_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    input_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PlanningPreview(Base):
    """Synthetic assessments cannot be promoted or confused with isolation runs."""
    __tablename__ = 'planning_preview'
    __table_args__ = (
        CheckConstraint("(inputs->>'mode' = 'synthetic' AND result->>'mode' = 'synthetic' AND result->>'executable' = 'false' AND result->>'status' = 'blocked') IS TRUE", name='planning_preview_synthetic_check'),
        CheckConstraint("input_hash ~ '^[0-9a-f]{64}$' AND result_hash ~ '^[0-9a-f]{64}$'", name='planning_preview_hash_check'),
        Index('planning_preview_actor_created_idx', 'actor_id', 'created_at'),
    )
    preview_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey('planning_preview.preview_id', ondelete='RESTRICT'))
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    result_hash: Mapped[str] = mapped_column(Text, nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    comparison: Mapped[dict | None] = mapped_column(JSONB)
