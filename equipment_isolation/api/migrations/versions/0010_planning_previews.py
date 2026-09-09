"""Immutable synthetic planning previews, separate from executable runs.

Revision ID: 0010_planning_previews
Revises: 0009_controlled_inputs
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = '0010_planning_previews'
down_revision = '0009_controlled_inputs'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('planning_preview',
        sa.Column('preview_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('parent_id', UUID(as_uuid=True), sa.ForeignKey('planning_preview.preview_id', ondelete='RESTRICT')),
        sa.Column('actor_id', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('input_hash', sa.Text(), nullable=False),
        sa.Column('result_hash', sa.Text(), nullable=False),
        sa.Column('inputs', JSONB(), nullable=False),
        sa.Column('result', JSONB(), nullable=False),
        sa.Column('comparison', JSONB()),
        sa.CheckConstraint("(inputs->>'mode' = 'synthetic' AND result->>'mode' = 'synthetic' AND result->>'executable' = 'false' AND result->>'status' = 'blocked') IS TRUE", name='planning_preview_synthetic_check'),
        sa.CheckConstraint("input_hash ~ '^[0-9a-f]{64}$' AND result_hash ~ '^[0-9a-f]{64}$'", name='planning_preview_hash_check'))
    op.create_index('planning_preview_actor_created_idx', 'planning_preview', ['actor_id', 'created_at'])
    op.execute('''CREATE FUNCTION guard_planning_preview() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'Planning previews are immutable'; END IF;
      IF NEW.parent_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM planning_preview WHERE preview_id = NEW.parent_id AND actor_id = NEW.actor_id
      ) THEN RAISE EXCEPTION 'Preview parent owner mismatch'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('CREATE TRIGGER planning_preview_guard BEFORE INSERT OR UPDATE OR DELETE ON planning_preview FOR EACH ROW EXECUTE FUNCTION guard_planning_preview()')


def downgrade():
    # Destructive: only use on an empty disposable database; deployment uses forward fixes.
    op.drop_table('planning_preview')
    op.execute('DROP FUNCTION guard_planning_preview()')
