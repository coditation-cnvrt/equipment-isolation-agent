"""Add shared operational conditions for assets.

Revision ID: 0006_shared_asset_conditions
Revises: 0005_feedback_constraint_names
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0006_shared_asset_conditions"
down_revision = "0005_feedback_constraint_names"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "asset_condition",
        sa.Column("condition_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("asset_ref_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("condition_type", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="active", nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_system", sa.Text(), nullable=True),
        sa.Column("source_reference", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("reported_by", sa.Text(), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("confirmed_by", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleared_by", sa.Text(), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("clear_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("condition_type IN ('unavailable')", name="asset_condition_type_check"),
        sa.CheckConstraint("state IN ('active','cleared')", name="asset_condition_state_check"),
        sa.ForeignKeyConstraint(["asset_ref_id"], ["asset_reference.asset_ref_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("condition_id"),
    )
    op.create_index(
        "asset_condition_one_active_type_idx",
        "asset_condition",
        ["asset_ref_id", "condition_type"],
        unique=True,
        postgresql_where=sa.text("state = 'active'"),
    )
    op.create_index(
        "asset_condition_state_reported_idx",
        "asset_condition",
        ["state", sa.text("reported_at DESC")],
        unique=False,
    )
    op.create_table(
        "asset_condition_event",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("condition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint("event_type IN ('reported','confirmed','cleared')", name="asset_condition_event_type_check"),
        sa.ForeignKeyConstraint(["condition_id"], ["asset_condition.condition_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "asset_condition_event_condition_idx",
        "asset_condition_event",
        ["condition_id", "occurred_at"],
        unique=False,
    )
    op.create_table(
        "plan_version_asset_condition",
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("condition_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["condition_id"], ["asset_condition.condition_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_version.plan_version_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("plan_version_id", "condition_id"),
    )


def downgrade():
    op.drop_table("plan_version_asset_condition")
    op.drop_index("asset_condition_event_condition_idx", table_name="asset_condition_event")
    op.drop_table("asset_condition_event")
    op.drop_index("asset_condition_state_reported_idx", table_name="asset_condition")
    op.drop_index("asset_condition_one_active_type_idx", table_name="asset_condition", postgresql_where=sa.text("state = 'active'"))
    op.drop_table("asset_condition")
