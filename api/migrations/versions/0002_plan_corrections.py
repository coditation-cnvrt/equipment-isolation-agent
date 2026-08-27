"""Normalize plan versions and add controlled correction derivations.

Revision ID: 0002_plan_corrections
Revises: 0001_current_schema
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_plan_corrections"
down_revision = "0001_current_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("isolation_runs", sa.Column("parent_run_id", sa.Text()))
    op.create_foreign_key("isolation_runs_parent_run_id_fkey", "isolation_runs", "isolation_runs", ["parent_run_id"], ["run_id"], ondelete="RESTRICT")
    op.create_index("isolation_runs_parent_run_idx", "isolation_runs", ["parent_run_id", sa.text("created_at DESC")])
    op.add_column("plan_version", sa.Column("normalization_status", sa.Text(), nullable=False, server_default="legacy_incomplete"))
    op.add_column("plan_version", sa.Column("assurance_status", sa.Text()))
    op.add_column("plan_version", sa.Column("content", postgresql.JSONB()))

    op.create_table("asset_reference",
        sa.Column("asset_ref_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_system", sa.Text(), nullable=False), sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False), sa.Column("asset_class", sa.Text(), nullable=False, server_default=""),
        sa.Column("context", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.UniqueConstraint("external_system", "external_id", name="asset_reference_external_key"))
    op.create_table("work_scope",
        sa.Column("work_scope_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False))
    op.create_table("work_scope_asset",
        sa.Column("work_scope_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("work_scope.work_scope_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("asset_ref_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_reference.asset_ref_id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("scope_role", sa.Text(), nullable=False), sa.Column("selection_source", sa.Text(), nullable=False))
    op.create_table("input_snapshot",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False), sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False))
    op.create_table("isolation_branch",
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_key", sa.Text(), nullable=False), sa.Column("topology_signature", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("plan_version_id", "branch_key", name="isolation_branch_version_key"))
    op.create_table("isolation_point",
        sa.Column("isolation_point_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_ref_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("asset_reference.asset_ref_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("point_key", sa.Text(), nullable=False), sa.Column("provenance", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("plan_version_id", "point_key", name="isolation_point_version_key"))
    op.create_table("path_point",
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("isolation_branch.branch_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("isolation_point_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("isolation_point.isolation_point_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("path_order", sa.Integer(), nullable=False, server_default="0"))
    op.create_table("plan_step",
        sa.Column("step_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_key", sa.Text(), nullable=False), sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("plan_version_id", "step_key", name="plan_step_version_key"))
    op.create_table("finding",
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_key", sa.Text(), nullable=False), sa.Column("blocks_authorisation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("plan_version_id", "finding_key", name="finding_version_key"))
    op.create_table("change_request",
        sa.Column("change_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("isolation_plan.plan_id", ondelete="CASCADE"), nullable=False),
        sa.Column("raised_against_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False), sa.Column("target_type", sa.Text(), nullable=False), sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("proposed_change", postgresql.JSONB(), nullable=False), sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="submitted"), sa.Column("raised_by", sa.Text(), nullable=False), sa.Column("approved_by", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("state IN ('submitted','approved','rejected','applied','superseded')", name="change_request_state_check"))
    op.create_index("change_request_plan_state_idx", "change_request", ["plan_id", "state", sa.text("created_at DESC")])
    op.create_table("derivation_manifest",
        sa.Column("manifest_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("isolation_plan.plan_id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_plan_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("run_id", sa.Text(), sa.ForeignKey("isolation_runs.run_id", ondelete="RESTRICT"), unique=True),
        sa.Column("child_plan_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT"), unique=True),
        sa.Column("state", sa.Text(), nullable=False), sa.Column("policy_hash", sa.Text(), nullable=False), sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)), sa.Column("error", postgresql.JSONB()),
        sa.CheckConstraint("state IN ('locked','running','completed','failed')", name="derivation_manifest_state_check"))
    op.create_index("derivation_manifest_plan_state_idx", "derivation_manifest", ["plan_id", "state"])
    op.create_table("derivation_manifest_change",
        sa.Column("manifest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("derivation_manifest.manifest_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("change_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("change_request.change_id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("required_effects", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))
    op.create_table("plan_version_change",
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("change_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("change_request.change_id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("application_outcome", sa.Text(), nullable=False), sa.Column("derivation_note", sa.Text()),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("change_coverage_result",
        sa.Column("coverage_result_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("manifest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("derivation_manifest.manifest_id", ondelete="CASCADE"), nullable=False),
        sa.Column("change_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("change_request.change_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False), sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("manifest_id", "change_id", name="change_coverage_manifest_change_key"))
    op.create_table("audit_event",
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("isolation_plan.plan_id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="RESTRICT")),
        sa.Column("event_type", sa.Text(), nullable=False), sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("payload", postgresql.JSONB(), nullable=False), sa.Column("previous_hash", sa.Text()), sa.Column("event_hash", sa.Text(), nullable=False, unique=True))


def downgrade():
    for table in ("audit_event", "change_coverage_result", "plan_version_change", "derivation_manifest_change"):
        op.drop_table(table)
    op.drop_index("derivation_manifest_plan_state_idx", table_name="derivation_manifest")
    op.drop_table("derivation_manifest")
    op.drop_index("change_request_plan_state_idx", table_name="change_request")
    for table in ("change_request", "finding", "plan_step", "path_point", "isolation_point", "isolation_branch", "input_snapshot", "work_scope_asset", "work_scope", "asset_reference"):
        op.drop_table(table)
    op.drop_column("plan_version", "content")
    op.drop_column("plan_version", "assurance_status")
    op.drop_column("plan_version", "normalization_status")
    op.drop_index("isolation_runs_parent_run_idx", table_name="isolation_runs")
    op.drop_constraint("isolation_runs_parent_run_id_fkey", "isolation_runs", type_="foreignkey")
    op.drop_column("isolation_runs", "parent_run_id")
