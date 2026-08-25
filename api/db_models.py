"""SQLAlchemy ORM mappings for the equipment-isolation PostgreSQL schema."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
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
