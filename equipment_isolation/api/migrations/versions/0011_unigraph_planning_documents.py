"""Pin UniGraph planning documents and retain durable event receipts.

Revision ID: 0011_unigraph_planning_documents
Revises: 0010_planning_previews
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0011_unigraph_planning_documents"
down_revision = "0010_planning_previews"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("derivation_manifest_trigger_kind_check", "derivation_manifest", type_="check")
    op.create_check_constraint(
        "derivation_manifest_trigger_kind_check",
        "derivation_manifest",
        "trigger_kind IN ('corrections','asset_conditions','source_data_defects','planning_inputs','combined')",
    )
    op.create_table(
        "planning_document_head",
        sa.Column("source_id", sa.Text(), primary_key=True),
        sa.Column("cnvrt_project_id", sa.Text(), primary_key=True),
        sa.Column("document_type", sa.Text(), primary_key=True),
        sa.Column("register_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_id", sa.BigInteger()),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.Text()),
        sa.Column("event_id", sa.Text()),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("document_type IN ('fhr','sic','psd')", name="planning_document_head_type_check"),
        sa.CheckConstraint("generation >= 0", name="planning_document_head_generation_check"),
    )
    op.create_table(
        "plan_version_planning_document",
        sa.Column("plan_version_id", UUID(as_uuid=True), sa.ForeignKey("plan_version.plan_version_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("document_type", sa.Text(), primary_key=True),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("cnvrt_project_id", sa.Text(), nullable=False),
        sa.Column("entry_unigraph_project_id", sa.Text(), nullable=False),
        sa.Column("register_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=False),
        sa.Column("revision_number", sa.BigInteger(), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("adapted_content_hash", sa.Text(), nullable=False),
        sa.Column("approval_snapshot", JSONB(), nullable=False),
        sa.Column("source_snapshot", JSONB(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("document_type IN ('fhr','sic','psd')", name="plan_version_planning_document_type_check"),
        sa.CheckConstraint("generation >= 0", name="plan_version_planning_document_generation_check"),
    )
    op.create_index(
        "plan_version_planning_document_head_idx",
        "plan_version_planning_document",
        ["source_id", "cnvrt_project_id", "document_type", "generation"],
    )
    op.create_table(
        "planning_document_event_receipt",
        sa.Column("source_id", sa.Text(), primary_key=True),
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("change_id", sa.Text()),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('processed','ignored','quarantined')", name="planning_document_event_receipt_status_check"),
    )
    op.create_index("planning_document_event_receipt_change_idx", "planning_document_event_receipt", ["change_id"])
    op.execute('''CREATE FUNCTION guard_plan_version_planning_document() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Plan planning-document snapshots are immutable'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER plan_version_planning_document_guard BEFORE UPDATE OR DELETE ON plan_version_planning_document FOR EACH ROW EXECUTE FUNCTION guard_plan_version_planning_document()')
    op.execute('''CREATE FUNCTION guard_planning_document_event_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Planning-document event receipts are immutable'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER planning_document_event_receipt_guard BEFORE UPDATE OR DELETE ON planning_document_event_receipt FOR EACH ROW EXECUTE FUNCTION guard_planning_document_event_receipt()')


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS planning_document_event_receipt_guard ON planning_document_event_receipt")
    op.execute("DROP FUNCTION IF EXISTS guard_planning_document_event_receipt()")
    op.execute("DROP TRIGGER IF EXISTS plan_version_planning_document_guard ON plan_version_planning_document")
    op.execute("DROP FUNCTION IF EXISTS guard_plan_version_planning_document()")
    op.drop_table("planning_document_event_receipt")
    op.drop_table("plan_version_planning_document")
    op.drop_table("planning_document_head")
    op.drop_constraint("derivation_manifest_trigger_kind_check", "derivation_manifest", type_="check")
    op.create_check_constraint(
        "derivation_manifest_trigger_kind_check",
        "derivation_manifest",
        "trigger_kind IN ('corrections','asset_conditions','source_data_defects','combined')",
    )
