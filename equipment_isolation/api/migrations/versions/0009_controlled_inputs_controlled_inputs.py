"""controlled inputs

Revision ID: 0009_controlled_inputs
Revises: 0008_source_data_defects
Create Date: 2026-09-08 15:14:22.717451
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0009_controlled_inputs'
down_revision: Union[str, Sequence[str], None] = '0008_source_data_defects'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Generated table DDL reviewed; cyclic head FK and guards added explicitly.
    op.create_table('controlled_input',
    sa.Column('input_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('input_type', sa.Text(), nullable=False),
    sa.Column('cnvrt_project_id', sa.Text(), nullable=False),
    sa.Column('collection_id', sa.Text(), nullable=False),
    sa.Column('job_id', sa.Text(), nullable=False),
    sa.Column('document_key', sa.Text(), nullable=False),
    sa.Column('created_by', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('approved_revision_id', sa.UUID(), nullable=True),
    sa.CheckConstraint("(input_type = 'fhr' AND length(btrim(job_id)) > 0) OR (input_type = 'sic' AND job_id = '')", name='controlled_input_scope_check'),
    sa.CheckConstraint("input_type IN ('fhr','sic')", name='controlled_input_type_check'),
    sa.CheckConstraint('length(btrim(cnvrt_project_id)) > 0 AND length(btrim(collection_id)) > 0 AND length(btrim(document_key)) > 0 AND length(btrim(created_by)) > 0', name='controlled_input_identity_check'),
    sa.PrimaryKeyConstraint('input_id'),
    sa.UniqueConstraint('input_type', 'cnvrt_project_id', 'collection_id', 'job_id', name='controlled_input_scope_key')
    )
    op.create_table('controlled_input_revision',
    sa.Column('revision_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('input_id', sa.UUID(), nullable=False),
    sa.Column('revision_label', sa.Text(), nullable=False),
    sa.Column('schema_version', sa.Text(), nullable=False),
    sa.Column('canonical_version', sa.Text(), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('content_hash', sa.Text(), nullable=False),
    sa.Column('validation', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('submitted_by', sa.Text(), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('decision', sa.Text(), server_default='pending', nullable=False),
    sa.Column('decided_by', sa.Text(), nullable=True),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_reason', sa.Text(), nullable=True),
    sa.CheckConstraint("(decision = 'pending' AND decided_by IS NULL AND decided_at IS NULL AND decision_reason IS NULL) OR (decision <> 'pending' AND decided_by IS NOT NULL AND decision_reason IS NOT NULL AND length(btrim(decided_by)) > 0 AND decided_at IS NOT NULL AND length(btrim(decision_reason)) > 0)", name='controlled_revision_metadata_check'),
    sa.CheckConstraint("canonical_version = 'controlled-json-v1'", name='controlled_revision_canonical_check'),
    sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name='controlled_revision_hash_check'),
    sa.CheckConstraint("decision IN ('pending','approved','rejected')", name='controlled_revision_decision_check'),
    sa.CheckConstraint('length(btrim(revision_label)) > 0 AND length(btrim(schema_version)) > 0 AND length(btrim(submitted_by)) > 0', name='controlled_revision_identity_check'),
    sa.ForeignKeyConstraint(['input_id'], ['controlled_input.input_id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('revision_id'),
    sa.UniqueConstraint('input_id', 'revision_id', name='controlled_revision_parent_key'),
    sa.UniqueConstraint('input_id', 'revision_label', name='controlled_revision_label_key')
    )
    op.create_table('run_input_manifest',
    sa.Column('manifest_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('run_id', sa.Text(), nullable=False),
    sa.Column('mode', sa.Text(), nullable=False),
    sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('semantic_request', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('request_hash', sa.Text(), nullable=False),
    sa.Column('manifest_hash', sa.Text(), nullable=False),
    sa.Column('schema_version', sa.Text(), nullable=False),
    sa.Column('canonical_version', sa.Text(), nullable=False),
    sa.Column('plan_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completeness', sa.Text(), nullable=False),
    sa.Column('missing_sources', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("jsonb_typeof(missing_sources) = 'array' AND jsonb_array_length(missing_sources) > 0", name='run_input_manifest_missing_check'),
    sa.CheckConstraint("mode = 'foundation' AND completeness = 'incomplete'", name='run_input_manifest_foundation_check'),
    sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$' AND manifest_hash ~ '^[0-9a-f]{64}$'", name='run_input_manifest_hash_check'),
    sa.CheckConstraint("schema_version = 'run-input-manifest-v1' AND canonical_version = 'controlled-json-v1'", name='run_input_manifest_schema_check'),
    sa.ForeignKeyConstraint(['run_id'], ['isolation_runs.run_id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('manifest_id'),
    sa.UniqueConstraint('run_id', name='run_input_manifest_run_key')
    )
    op.create_table('plan_version_invalidation',
    sa.Column('plan_version_id', sa.UUID(), nullable=False),
    sa.Column('consumed_revision_id', sa.UUID(), nullable=False),
    sa.Column('replacement_revision_id', sa.UUID(), nullable=False),
    sa.Column('input_id', sa.UUID(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("consumed_revision_id <> replacement_revision_id AND reason = 'approved_revision_replaced'", name='plan_invalidation_reason_check'),
    sa.ForeignKeyConstraint(['input_id', 'consumed_revision_id'], ['controlled_input_revision.input_id', 'controlled_input_revision.revision_id'], name='plan_invalidation_consumed_fk', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['input_id', 'replacement_revision_id'], ['controlled_input_revision.input_id', 'controlled_input_revision.revision_id'], name='plan_invalidation_replacement_fk', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plan_version_id'], ['plan_version.plan_version_id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('plan_version_id', 'consumed_revision_id', 'replacement_revision_id')
    )
    op.create_table('run_input_manifest_item',
    sa.Column('manifest_id', sa.UUID(), nullable=False),
    sa.Column('input_type', sa.Text(), nullable=False),
    sa.Column('role', sa.Text(), nullable=False),
    sa.Column('input_id', sa.UUID(), nullable=False),
    sa.Column('revision_id', sa.UUID(), nullable=False),
    sa.Column('content_hash', sa.Text(), nullable=False),
    sa.Column('schema_version', sa.Text(), nullable=False),
    sa.Column('approval_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name='run_input_item_hash_check'),
    sa.CheckConstraint("input_type IN ('fhr','sic') AND role = 'source'", name='run_input_item_slot_check'),
    sa.ForeignKeyConstraint(['input_id', 'revision_id'], ['controlled_input_revision.input_id', 'controlled_input_revision.revision_id'], name='run_input_item_revision_fk', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['manifest_id'], ['run_input_manifest.manifest_id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('manifest_id', 'input_type', 'role')
    )
    op.create_index('run_input_item_revision_idx', 'run_input_manifest_item', ['input_id', 'revision_id'], unique=False)
    op.create_foreign_key('controlled_input_head_fk', 'controlled_input', 'controlled_input_revision', ['input_id', 'approved_revision_id'], ['input_id', 'revision_id'], ondelete='RESTRICT')
    _install_guards()


def downgrade() -> None:
    # Empty disposable databases only; populated deployments use backup/forward fixes.
    op.execute("DROP TRIGGER controlled_promotion_guard ON external_run_link")
    op.execute("DROP TRIGGER controlled_link_guard ON external_run_link")
    op.drop_constraint('controlled_input_head_fk', 'controlled_input', type_='foreignkey')
    op.drop_index('run_input_item_revision_idx', table_name='run_input_manifest_item')
    op.drop_table('run_input_manifest_item')
    op.drop_table('plan_version_invalidation')
    op.drop_table('run_input_manifest')
    op.drop_table('controlled_input_revision')
    op.drop_table('controlled_input')
    for name in ('controlled_revision_guard', 'controlled_document_guard',
                 'controlled_manifest_guard', 'controlled_manifest_commit_guard',
                 'controlled_item_guard', 'controlled_invalidation_guard',
                 'controlled_head_invalidate', 'controlled_promotion_invalidate',
                 'controlled_link_guard', 'controlled_decision_commit_guard'):
        op.execute(f"DROP FUNCTION {name}()")


def _install_guards():
    op.execute("""
    CREATE FUNCTION controlled_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'controlled revisions cannot be deleted'; END IF;
        IF TG_OP = 'INSERT' THEN
            IF NEW.decision <> 'pending' THEN RAISE EXCEPTION 'submit before deciding'; END IF;
            RETURN NEW;
        END IF;
        IF OLD.decision <> 'pending' OR NEW.decision NOT IN ('approved','rejected') OR
           (to_jsonb(NEW) - ARRAY['decision','decided_by','decided_at','decision_reason']) IS DISTINCT FROM
           (to_jsonb(OLD) - ARRAY['decision','decided_by','decided_at','decision_reason']) THEN
            RAISE EXCEPTION 'only a single terminal decision is permitted';
        END IF;
        IF NEW.decision = 'approved' AND
           (NEW.schema_version <> 'fhr-v1' OR NEW.validation->>'status' IS DISTINCT FROM 'valid' OR
            lower(NEW.payload->'document'->>'status') LIKE '%mock%' OR
            upper(NEW.payload->'document'->>'revision') LIKE 'MOCK-%' OR
            NEW.payload->'metadata'->>'synthetic' = 'true' OR
            NOT EXISTS (SELECT 1 FROM controlled_input WHERE input_id = NEW.input_id AND input_type = 'fhr')) THEN
            RAISE EXCEPTION 'unsupported or synthetic input cannot be approved';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER controlled_revision_guard BEFORE INSERT OR UPDATE OR DELETE ON controlled_input_revision
      FOR EACH ROW EXECUTE FUNCTION controlled_revision_guard();

    CREATE FUNCTION controlled_decision_commit_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.decision = 'approved' AND NOT EXISTS (
            SELECT 1 FROM controlled_input WHERE input_id = NEW.input_id AND approved_revision_id = NEW.revision_id
        ) THEN RAISE EXCEPTION 'approval must replace the head atomically'; END IF;
        RETURN NULL;
    END $$;
    CREATE CONSTRAINT TRIGGER controlled_decision_commit_guard AFTER UPDATE ON controlled_input_revision
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION controlled_decision_commit_guard();

    CREATE FUNCTION controlled_document_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'controlled document identity is immutable'; END IF;
        IF TG_OP = 'INSERT' THEN
            IF NEW.approved_revision_id IS NOT NULL THEN RAISE EXCEPTION 'new document cannot have a head'; END IF;
            RETURN NEW;
        END IF;
        IF (to_jsonb(NEW) - 'approved_revision_id') IS DISTINCT FROM (to_jsonb(OLD) - 'approved_revision_id') OR
           NEW.approved_revision_id IS NULL OR NEW.approved_revision_id IS NOT DISTINCT FROM OLD.approved_revision_id THEN
            RAISE EXCEPTION 'only head replacement is permitted';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM controlled_input_revision r WHERE r.input_id = NEW.input_id
                       AND r.revision_id = NEW.approved_revision_id AND r.decision = 'approved') THEN
            RAISE EXCEPTION 'head must be an approved revision of this document';
        END IF;
        IF OLD.approved_revision_id IS NOT NULL AND
           (SELECT decided_at FROM controlled_input_revision WHERE revision_id = NEW.approved_revision_id) <=
           (SELECT decided_at FROM controlled_input_revision WHERE revision_id = OLD.approved_revision_id) THEN
            RAISE EXCEPTION 'cannot roll head back to an earlier decision';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER controlled_document_guard BEFORE INSERT OR UPDATE OR DELETE ON controlled_input
      FOR EACH ROW EXECUTE FUNCTION controlled_document_guard();

    CREATE FUNCTION controlled_manifest_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE r isolation_runs;
    BEGIN
        IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'manifest is immutable'; END IF;
        IF TG_OP = 'INSERT' THEN
            SELECT * INTO r FROM isolation_runs WHERE run_id = NEW.run_id FOR UPDATE;
            IF r.run_id IS NULL OR r.status <> 'queued' OR r.started_at IS NOT NULL OR NEW.locked_at IS NOT NULL THEN
                RAISE EXCEPTION 'manifest must be assembled before execution';
            END IF;
            IF NEW.context->>'cnvrt_project_id' IS DISTINCT FROM r.request->>'cnvrt_project_id' OR
               NEW.context->>'collection_id' IS DISTINCT FROM r.request->>'collection_id' OR
               NEW.context->>'job_id' IS DISTINCT FROM r.request->>'job_id' THEN
                RAISE EXCEPTION 'manifest scope must match persisted run';
            END IF;
            RETURN NEW;
        END IF;
        IF OLD.locked_at IS NOT NULL OR NEW.locked_at IS NULL OR
           (to_jsonb(NEW) - 'locked_at') IS DISTINCT FROM (to_jsonb(OLD) - 'locked_at') THEN
            RAISE EXCEPTION 'manifest is immutable after locking';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER controlled_manifest_guard BEFORE INSERT OR UPDATE OR DELETE ON run_input_manifest
      FOR EACH ROW EXECUTE FUNCTION controlled_manifest_guard();

    CREATE FUNCTION controlled_manifest_commit_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM run_input_manifest WHERE manifest_id = NEW.manifest_id AND locked_at IS NOT NULL) THEN
            RAISE EXCEPTION 'an unlocked manifest cannot commit';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM run_input_manifest_item WHERE manifest_id = NEW.manifest_id) THEN
            RAISE EXCEPTION 'a foundation manifest needs at least one approved pin';
        END IF;
        RETURN NULL;
    END $$;
    CREATE CONSTRAINT TRIGGER controlled_manifest_commit_guard AFTER INSERT ON run_input_manifest
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION controlled_manifest_commit_guard();

    CREATE FUNCTION controlled_item_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE m run_input_manifest; d controlled_input; r controlled_input_revision;
    BEGIN
        IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'manifest items are immutable'; END IF;
        SELECT * INTO m FROM run_input_manifest WHERE manifest_id = NEW.manifest_id FOR UPDATE;
        IF m.manifest_id IS NULL OR m.locked_at IS NOT NULL THEN RAISE EXCEPTION 'manifest is absent or locked'; END IF;
        SELECT * INTO d FROM controlled_input WHERE input_id = NEW.input_id FOR UPDATE;
        SELECT * INTO r FROM controlled_input_revision WHERE revision_id = NEW.revision_id;
        IF d.input_id IS NULL OR r.revision_id IS NULL OR r.input_id <> d.input_id OR
           r.decision <> 'approved' OR d.approved_revision_id IS DISTINCT FROM r.revision_id OR
           NEW.input_type <> d.input_type OR NEW.content_hash <> r.content_hash OR NEW.schema_version <> r.schema_version OR
           d.cnvrt_project_id IS DISTINCT FROM m.context->>'cnvrt_project_id' OR
           d.collection_id IS DISTINCT FROM m.context->>'collection_id' OR
           (d.input_type = 'fhr' AND d.job_id IS DISTINCT FROM m.context->>'job_id') OR
           NEW.approval_snapshot->>'decision' IS DISTINCT FROM r.decision OR
           NEW.approval_snapshot->>'decided_by' IS DISTINCT FROM r.decided_by OR
           NEW.approval_snapshot->>'decision_reason' IS DISTINCT FROM r.decision_reason OR
           NEW.approval_snapshot->>'decided_at' IS NULL OR
           (NEW.approval_snapshot->>'decided_at')::timestamptz IS DISTINCT FROM r.decided_at THEN
            RAISE EXCEPTION 'manifest pin must match current approved content, scope and decision';
        END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER controlled_item_guard BEFORE INSERT OR UPDATE OR DELETE ON run_input_manifest_item
      FOR EACH ROW EXECUTE FUNCTION controlled_item_guard();

    CREATE FUNCTION controlled_invalidation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'invalidations are append-only'; END IF;
        IF NOT EXISTS (
            SELECT 1 FROM external_run_link e JOIN run_input_manifest m ON m.run_id = e.run_id
            JOIN run_input_manifest_item i ON i.manifest_id = m.manifest_id
            JOIN controlled_input_revision replacement ON replacement.revision_id = NEW.replacement_revision_id
            JOIN controlled_input_revision consumed ON consumed.revision_id = NEW.consumed_revision_id
            WHERE e.plan_version_id = NEW.plan_version_id AND e.link_role = 'derivation' AND m.locked_at IS NOT NULL
            AND i.input_id = NEW.input_id AND i.revision_id = NEW.consumed_revision_id
            AND replacement.input_id = NEW.input_id AND replacement.decision = 'approved'
            AND replacement.decided_at > consumed.decided_at
        ) THEN RAISE EXCEPTION 'invalidation must reference consumed content and a later approved revision'; END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER controlled_invalidation_guard BEFORE INSERT OR UPDATE OR DELETE ON plan_version_invalidation
      FOR EACH ROW EXECUTE FUNCTION controlled_invalidation_guard();

    CREATE FUNCTION controlled_head_invalidate() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        INSERT INTO plan_version_invalidation (plan_version_id, input_id, consumed_revision_id, replacement_revision_id, reason)
        SELECT e.plan_version_id, NEW.input_id, i.revision_id, NEW.approved_revision_id, 'approved_revision_replaced'
        FROM run_input_manifest_item i JOIN run_input_manifest m USING (manifest_id)
        JOIN external_run_link e ON e.run_id = m.run_id AND e.link_role = 'derivation'
        WHERE i.input_id = NEW.input_id AND i.revision_id <> NEW.approved_revision_id
        ON CONFLICT DO NOTHING;
        RETURN NULL;
    END $$;
    CREATE TRIGGER controlled_head_invalidate AFTER UPDATE OF approved_revision_id ON controlled_input
      FOR EACH ROW EXECUTE FUNCTION controlled_head_invalidate();

    CREATE FUNCTION controlled_link_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF EXISTS (SELECT 1 FROM run_input_manifest WHERE run_id = OLD.run_id) OR
           (TG_OP = 'UPDATE' AND EXISTS (SELECT 1 FROM run_input_manifest WHERE run_id = NEW.run_id)) THEN
            RAISE EXCEPTION 'controlled run provenance links are immutable';
        END IF;
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END $$;
    CREATE TRIGGER controlled_link_guard BEFORE UPDATE OR DELETE ON external_run_link
      FOR EACH ROW EXECUTE FUNCTION controlled_link_guard();

    CREATE FUNCTION controlled_promotion_invalidate() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
        IF NEW.link_role <> 'derivation' THEN RETURN NULL; END IF;
        -- Same document locks as approval; statements after the wait see committed heads.
        PERFORM d.input_id FROM controlled_input d
        JOIN run_input_manifest_item i USING (input_id)
        JOIN run_input_manifest m USING (manifest_id)
        WHERE m.run_id = NEW.run_id ORDER BY d.input_id FOR UPDATE OF d;
        INSERT INTO plan_version_invalidation (plan_version_id, input_id, consumed_revision_id, replacement_revision_id, reason)
        SELECT NEW.plan_version_id, d.input_id, i.revision_id, d.approved_revision_id, 'approved_revision_replaced'
        FROM controlled_input d JOIN run_input_manifest_item i USING (input_id)
        JOIN run_input_manifest m USING (manifest_id)
        WHERE m.run_id = NEW.run_id AND d.approved_revision_id <> i.revision_id
        ON CONFLICT DO NOTHING;
        RETURN NULL;
    END $$;
    CREATE TRIGGER controlled_promotion_guard AFTER INSERT ON external_run_link
      FOR EACH ROW EXECUTE FUNCTION controlled_promotion_invalidate();
    """)
