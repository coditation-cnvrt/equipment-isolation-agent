"""Establish the packaged equipment-isolation schema migration baseline.

Revision ID: 0001_current_schema
Revises: None
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_current_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "isolation_runs",
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("equipment_tag", sa.Text(), nullable=False),
        sa.Column("runner", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("request", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("agent", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("trace", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("error", postgresql.JSONB(astext_type=sa.Text())),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="isolation_runs_status_check",
        ),
        sa.PrimaryKeyConstraint("run_id", name="isolation_runs_pkey"),
    )
    runs = sa.table(
        "isolation_runs",
        sa.column("equipment_tag", sa.Text()),
        sa.column("status", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("request", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.create_index(
        "isolation_runs_status_idx",
        "isolation_runs",
        [runs.c.status, runs.c.created_at.desc()],
    )
    op.create_index(
        "isolation_runs_equipment_idx",
        "isolation_runs",
        [runs.c.equipment_tag, runs.c.created_at.desc()],
    )

    op.create_table(
        "isolation_run_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("event", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["isolation_runs.run_id"],
            name="isolation_run_events_run_id_fkey",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="isolation_run_events_pkey"),
    )
    op.create_index(
        "isolation_run_events_run_id_id_idx",
        "isolation_run_events",
        ["run_id", "id"],
    )

    op.execute(sa.schema.CreateSequence(sa.Sequence("isolation_plan_number_seq")))
    op.create_table(
        "isolation_plan",
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.func.gen_random_uuid(),
        ),
        sa.Column("plan_number", sa.Text(), nullable=False),
        sa.Column("active_plan_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("mode", sa.Text(), nullable=False, server_default="advisory"),
        sa.Column("lifecycle_state", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("area_code", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("mode IN ('advisory')", name="isolation_plan_mode_check"),
        sa.CheckConstraint(
            "lifecycle_state IN ('draft')",
            name="isolation_plan_lifecycle_state_check",
        ),
        sa.PrimaryKeyConstraint("plan_id", name="isolation_plan_pkey"),
        sa.UniqueConstraint("plan_number", name="isolation_plan_plan_number_key"),
    )

    op.create_table(
        "plan_version",
        sa.Column(
            "plan_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.func.gen_random_uuid(),
        ),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_plan_version_id", postgresql.UUID(as_uuid=True)),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("derivation_status", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("model_hash", sa.Text(), nullable=False),
        sa.Column(
            "derived_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("superseded_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("version_no > 0", name="plan_version_version_no_check"),
        sa.CheckConstraint(
            "derivation_status IN ('completed', 'completed_degraded')",
            name="plan_version_derivation_status_check",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["isolation_plan.plan_id"],
            name="plan_version_plan_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id", "parent_plan_version_id"],
            ["plan_version.plan_id", "plan_version.plan_version_id"],
            name="plan_version_plan_id_parent_plan_version_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("plan_version_id", name="plan_version_pkey"),
        sa.UniqueConstraint(
            "plan_id", "version_no", name="plan_version_plan_id_version_no_key"
        ),
        sa.UniqueConstraint(
            "plan_id",
            "plan_version_id",
            name="plan_version_plan_id_plan_version_id_key",
        ),
    )
    op.create_foreign_key(
        "isolation_plan_active_version_fk",
        "isolation_plan",
        "plan_version",
        ["plan_id", "active_plan_version_id"],
        ["plan_id", "plan_version_id"],
        ondelete="RESTRICT",
    )

    op.create_table(
        "external_run_link",
        sa.Column(
            "run_link_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.func.gen_random_uuid(),
        ),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("runner", sa.Text(), nullable=False),
        sa.Column("link_role", sa.Text(), nullable=False),
        sa.Column("result_uri", sa.Text(), nullable=False),
        sa.Column("trace_uri", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "link_role IN ('derivation', 'validation', 'comparison')",
            name="external_run_link_link_role_check",
        ),
        sa.ForeignKeyConstraint(
            ["plan_version_id"],
            ["plan_version.plan_version_id"],
            name="external_run_link_plan_version_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["isolation_runs.run_id"],
            name="external_run_link_run_id_fkey",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("run_link_id", name="external_run_link_pkey"),
        sa.UniqueConstraint("run_id", name="external_run_link_run_id_key"),
    )
    external_links = sa.table(
        "external_run_link",
        sa.column("plan_version_id", postgresql.UUID(as_uuid=True)),
        sa.column("link_role", sa.Text()),
    )
    op.create_index(
        "external_run_link_one_derivation_idx",
        "external_run_link",
        [external_links.c.plan_version_id],
        unique=True,
        postgresql_where=external_links.c.link_role == "derivation",
    )

    plans = sa.table(
        "isolation_plan",
        sa.column("plan_id", postgresql.UUID(as_uuid=True)),
        sa.column("lifecycle_state", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    versions = sa.table(
        "plan_version",
        sa.column("plan_id", postgresql.UUID(as_uuid=True)),
        sa.column("version_no", sa.Integer()),
    )
    op.create_index(
        "isolation_plan_created_at_idx",
        "isolation_plan",
        [plans.c.created_at.desc(), plans.c.plan_id.desc()],
    )
    op.create_index(
        "isolation_plan_state_created_idx",
        "isolation_plan",
        [plans.c.lifecycle_state, plans.c.created_at.desc(), plans.c.plan_id.desc()],
    )
    op.create_index(
        "plan_version_plan_version_no_idx",
        "plan_version",
        [versions.c.plan_id, versions.c.version_no.desc()],
    )
    op.create_index(
        "isolation_runs_planning_context_idx",
        "isolation_runs",
        [
            runs.c.equipment_tag,
            runs.c.request["cnvrt_project_id"].astext,
            runs.c.request["collection_id"].astext,
            runs.c.request["job_id"].astext,
            runs.c.request["unigraph_project_id"].astext,
        ],
    )


def downgrade() -> None:
    op.drop_table("external_run_link")
    op.drop_constraint(
        "isolation_plan_active_version_fk", "isolation_plan", type_="foreignkey"
    )
    op.drop_table("plan_version")
    op.drop_table("isolation_plan")
    op.execute(sa.schema.DropSequence(sa.Sequence("isolation_plan_number_seq")))
    op.drop_table("isolation_run_events")
    op.drop_table("isolation_runs")
