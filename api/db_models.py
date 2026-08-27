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


class ChangeRequest(Base):
    __tablename__ = "change_request"
    __table_args__ = (
        CheckConstraint("state IN ('submitted','approved','rejected','applied','superseded')", name="change_request_state_check"),
    )
    change_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("isolation_plan.plan_id", ondelete="CASCADE"), nullable=False)
    raised_against_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"), nullable=False)
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_change: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="submitted")
    raised_by: Mapped[str] = mapped_column(Text, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DerivationManifest(Base):
    __tablename__ = "derivation_manifest"
    __table_args__ = (CheckConstraint("state IN ('locked','running','completed','failed')", name="derivation_manifest_state_check"),)
    manifest_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("isolation_plan.plan_id", ondelete="CASCADE"), nullable=False)
    parent_plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"), nullable=False)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("isolation_runs.run_id", ondelete="RESTRICT"), unique=True)
    child_plan_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"), unique=True)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    policy_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[Any | None] = mapped_column(JSONB)


class DerivationManifestChange(Base):
    __tablename__ = "derivation_manifest_change"
    manifest_id: Mapped[UUID] = mapped_column(ForeignKey("derivation_manifest.manifest_id", ondelete="CASCADE"), primary_key=True)
    change_id: Mapped[UUID] = mapped_column(ForeignKey("change_request.change_id", ondelete="RESTRICT"), primary_key=True)
    mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    required_effects: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")


class PlanVersionChange(Base):
    __tablename__ = "plan_version_change"
    plan_version_id: Mapped[UUID] = mapped_column(ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), primary_key=True)
    change_id: Mapped[UUID] = mapped_column(ForeignKey("change_request.change_id", ondelete="RESTRICT"), primary_key=True)
    application_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    derivation_note: Mapped[str | None] = mapped_column(Text)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChangeCoverageResult(Base):
    __tablename__ = "change_coverage_result"
    __table_args__ = (UniqueConstraint("manifest_id", "change_id", name="change_coverage_manifest_change_key"),)
    coverage_result_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    manifest_id: Mapped[UUID] = mapped_column(ForeignKey("derivation_manifest.manifest_id", ondelete="CASCADE"), nullable=False)
    change_id: Mapped[UUID] = mapped_column(ForeignKey("change_request.change_id", ondelete="RESTRICT"), nullable=False)
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
Index("change_request_plan_state_idx", ChangeRequest.plan_id, ChangeRequest.state, ChangeRequest.created_at.desc())
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
