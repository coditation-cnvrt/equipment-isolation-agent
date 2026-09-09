"""Add source-data defect governance workflow.

Revision ID: 0008_source_data_defects
Revises: 0007_asset_state_derivation
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0008_source_data_defects"
down_revision = "0007_asset_state_derivation"
branch_labels = None
depends_on = None


def upgrade():
    jsonb = postgresql.JSONB(astext_type=sa.Text())
    op.create_table(
        "source_data_defect",
        sa.Column("defect_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("cnvrt_project_id", sa.Text(), nullable=False),
        sa.Column("collection_id", sa.Text(), nullable=False),
        sa.Column("unigraph_project_id", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("reported_source_revision", sa.Text(), nullable=True),
        sa.Column("reported_source_snapshot_hash", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("anchor_type", sa.Text(), nullable=False),
        sa.Column("anchor_id", sa.Text(), nullable=False),
        sa.Column("anchor_facts", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="reported", nullable=False),
        sa.Column("policy_snapshot", jsonb, nullable=False),
        sa.Column("policy_hash", sa.Text(), nullable=False),
        sa.Column("reported_by", sa.Text(), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("claimed_by", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("state IN ('reported','confirmed','remediation_recorded','resolved','rejected','withdrawn')", name="source_data_defect_state_check"),
        sa.CheckConstraint("anchor_type IN ('entity','link','point','region')", name="source_data_defect_anchor_type_check"),
        sa.CheckConstraint("category IN ('missing_device','extra_device','incorrect_device_type','incorrect_symbol','incorrect_label','incorrect_attribute','missing_connection','phantom_connection','incorrect_connection','off_page_connector_mismatch','source_revision_mismatch','other')", name="source_data_defect_category_check"),
        sa.CheckConstraint("length(btrim(anchor_id)) > 0", name="source_data_defect_anchor_id_not_blank_check"),
        sa.CheckConstraint("length(btrim(description)) >= 3", name="source_data_defect_description_check"),
        sa.CheckConstraint("(claimed_by IS NULL) = (claimed_at IS NULL)", name="source_data_defect_claim_consistency_check"),
        sa.CheckConstraint("version > 0", name="source_data_defect_version_check"),
        sa.PrimaryKeyConstraint("defect_id"),
    )
    op.create_index("source_data_defect_scope_state_idx", "source_data_defect", ["cnvrt_project_id", "collection_id", "job_id", "state"])
    op.create_table(
        "source_data_defect_event",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("defect_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("from_state", sa.Text(), nullable=True),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("defect_version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("payload", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("previous_hash", sa.Text(), nullable=True),
        sa.Column("event_hash", sa.Text(), nullable=False),
        sa.CheckConstraint("event_type IN ('reported','confirmed','remediation_recorded','resolved','rejected','withdrawn','reopened','reclassified','commented','evidence_added','claimed','released')", name="source_data_defect_event_type_check"),
        sa.CheckConstraint("to_state IN ('reported','confirmed','remediation_recorded','resolved','rejected','withdrawn')", name="source_data_defect_event_to_state_check"),
        sa.CheckConstraint("from_state IS NULL OR from_state IN ('reported','confirmed','remediation_recorded','resolved','rejected','withdrawn')", name="source_data_defect_event_from_state_check"),
        sa.CheckConstraint("defect_version > 0", name="source_data_defect_event_version_check"),
        sa.ForeignKeyConstraint(["defect_id"], ["source_data_defect.defect_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint("defect_id", "defect_version", name="source_data_defect_event_version_key"),
        sa.UniqueConstraint("defect_id", "event_id", name="source_data_defect_event_defect_event_key"),
        sa.UniqueConstraint("event_hash", name="source_data_defect_event_event_hash_key"),
    )
    op.create_index("source_data_defect_event_scope_idx", "source_data_defect_event", ["defect_id", "occurred_at"])
    op.create_table(
        "plan_source_dependency",
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context", jsonb, nullable=False),
        sa.Column("manifest_status", sa.Text(), nullable=False),
        sa.Column("verified_source_revision", sa.Text(), nullable=True),
        sa.Column("verified_source_snapshot_hash", sa.Text(), nullable=True),
        sa.Column("provenance", jsonb, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("exact_anchor_ids", jsonb, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source_defect_ids", jsonb, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source_defect_snapshots", jsonb, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source_defect_event_ids", jsonb, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source_defect_event_watermark_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_defect_event_watermark_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_version_id"], ["plan_version.plan_version_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_defect_event_watermark_id"], ["source_data_defect_event.event_id"], ondelete="RESTRICT"),
        sa.CheckConstraint("manifest_status IN ('complete','incomplete','historical_unknown')", name="plan_source_dependency_status_check"),
        sa.PrimaryKeyConstraint("plan_version_id"),
    )
    op.execute(sa.text("""
        INSERT INTO plan_source_dependency (plan_version_id, context, manifest_status, provenance, exact_anchor_ids, source_defect_ids, source_defect_snapshots, source_defect_event_ids)
        SELECT pv.plan_version_id,
               jsonb_build_object(
                   'cnvrt_project_id', COALESCE(ir.request->>'cnvrt_project_id', ''),
                   'collection_id', COALESCE(ir.request->>'collection_id', ''),
                   'unigraph_project_id', COALESCE(ir.request->>'unigraph_project_id', ''),
                   'job_id', COALESCE(ir.request->>'job_id', '')
               ), 'historical_unknown', jsonb_build_object('source', 'migration_backfill'),
               '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb
        FROM plan_version pv
        JOIN external_run_link erl ON erl.plan_version_id = pv.plan_version_id AND erl.link_role = 'derivation'
        JOIN isolation_runs ir ON ir.run_id = erl.run_id
    """))
    op.create_table(
        "source_defect_plan_impact",
        sa.Column("impact_id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("defect_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("match_scope", sa.Text(), nullable=False),
        sa.Column("snapshot", jsonb, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("match_scope IN ('exact','drawing','drawing_fallback','source_revision')", name="source_defect_plan_impact_scope_check"),
        sa.ForeignKeyConstraint(["defect_id", "event_id"], ["source_data_defect_event.defect_id", "source_data_defect_event.event_id"], name="source_defect_plan_impact_defect_event_fkey", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id", "plan_version_id"], ["plan_version.plan_id", "plan_version.plan_version_id"], name="source_defect_plan_impact_plan_version_fkey", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("impact_id"),
        sa.UniqueConstraint("event_id", "plan_version_id", name="source_defect_plan_impact_event_version_key"),
    )
    op.create_index("source_defect_plan_impact_event_idx", "source_defect_plan_impact", ["event_id", "plan_version_id"])
    op.create_table(
        "derivation_manifest_source_data_defect",
        sa.Column("manifest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("defect_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot", jsonb, nullable=False),
        sa.ForeignKeyConstraint(["manifest_id"], ["derivation_manifest.manifest_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["defect_id", "event_id"], ["source_data_defect_event.defect_id", "source_data_defect_event.event_id"], name="derivation_manifest_source_defect_event_fkey", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("manifest_id", "defect_id"),
    )
    op.drop_constraint("derivation_manifest_trigger_kind_check", "derivation_manifest", type_="check")
    op.create_check_constraint(
        "derivation_manifest_trigger_kind_check",
        "derivation_manifest",
        "trigger_kind IN ('corrections','asset_conditions','source_data_defects','combined')",
    )
    op.execute(sa.text("""
        CREATE FUNCTION reject_source_data_defect_event_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
            RAISE EXCEPTION 'source_data_defect_event is append-only';
        END $$
    """))
    op.execute(sa.text("""
        CREATE TRIGGER source_data_defect_event_append_only
        BEFORE UPDATE OR DELETE ON source_data_defect_event
        FOR EACH ROW EXECUTE FUNCTION reject_source_data_defect_event_mutation()
    """))


def downgrade():
    op.execute("DROP TRIGGER source_data_defect_event_append_only ON source_data_defect_event")
    op.execute("DROP FUNCTION reject_source_data_defect_event_mutation()")
    op.drop_constraint("derivation_manifest_trigger_kind_check", "derivation_manifest", type_="check")
    op.create_check_constraint(
        "derivation_manifest_trigger_kind_check",
        "derivation_manifest",
        "trigger_kind IN ('corrections','asset_conditions','combined')",
    )
    op.drop_table("derivation_manifest_source_data_defect")
    op.drop_index("source_defect_plan_impact_event_idx", table_name="source_defect_plan_impact")
    op.drop_table("source_defect_plan_impact")
    op.drop_table("plan_source_dependency")
    op.drop_index("source_data_defect_event_scope_idx", table_name="source_data_defect_event")
    op.drop_table("source_data_defect_event")
    op.drop_index("source_data_defect_scope_state_idx", table_name="source_data_defect")
    op.drop_table("source_data_defect")
