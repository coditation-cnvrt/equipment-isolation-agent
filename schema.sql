CREATE TABLE IF NOT EXISTS isolation_runs (
    run_id TEXT PRIMARY KEY,
    equipment_tag TEXT NOT NULL,
    runner TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    created_at TIMESTAMPTZ NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    request JSONB NOT NULL,
    agent JSONB,
    result JSONB,
    trace JSONB,
    error JSONB
);

CREATE INDEX IF NOT EXISTS isolation_runs_status_idx
    ON isolation_runs (status, created_at DESC);

CREATE INDEX IF NOT EXISTS isolation_runs_equipment_idx
    ON isolation_runs (equipment_tag, created_at DESC);

CREATE TABLE IF NOT EXISTS isolation_run_events (
    id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES isolation_runs(run_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    event JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS isolation_run_events_run_id_id_idx
    ON isolation_run_events (run_id, id);

-- Stable advisory-plan identities and immutable derivation versions. The first
-- delivery slice promotes an already-succeeded isolation_run into version 1.
CREATE SEQUENCE IF NOT EXISTS isolation_plan_number_seq;

CREATE TABLE IF NOT EXISTS isolation_plan (
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_number TEXT NOT NULL UNIQUE,
    active_plan_version_id UUID,
    mode TEXT NOT NULL DEFAULT 'advisory' CHECK (mode IN ('advisory')),
    lifecycle_state TEXT NOT NULL DEFAULT 'draft' CHECK (lifecycle_state IN ('draft')),
    area_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plan_version (
    plan_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id UUID NOT NULL REFERENCES isolation_plan(plan_id) ON DELETE RESTRICT,
    parent_plan_version_id UUID,
    version_no INTEGER NOT NULL CHECK (version_no > 0),
    derivation_status TEXT NOT NULL CHECK (derivation_status IN ('completed', 'completed_degraded')),
    input_hash TEXT NOT NULL,
    model_hash TEXT NOT NULL,
    derived_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_at TIMESTAMPTZ,
    UNIQUE (plan_id, version_no),
    UNIQUE (plan_id, plan_version_id),
    FOREIGN KEY (plan_id, parent_plan_version_id)
        REFERENCES plan_version(plan_id, plan_version_id) ON DELETE RESTRICT
);

-- PostgreSQL has no ADD CONSTRAINT IF NOT EXISTS. The guarded block keeps the
-- development bootstrap idempotent; production should apply this as a versioned migration.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'isolation_plan_active_version_fk'
          AND conrelid = 'isolation_plan'::regclass
    ) THEN
        ALTER TABLE isolation_plan
            ADD CONSTRAINT isolation_plan_active_version_fk
            FOREIGN KEY (plan_id, active_plan_version_id)
            REFERENCES plan_version(plan_id, plan_version_id) ON DELETE RESTRICT;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS external_run_link (
    run_link_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_version_id UUID NOT NULL REFERENCES plan_version(plan_version_id) ON DELETE RESTRICT,
    run_id TEXT NOT NULL UNIQUE REFERENCES isolation_runs(run_id) ON DELETE RESTRICT,
    runner TEXT NOT NULL,
    link_role TEXT NOT NULL CHECK (link_role IN ('derivation', 'validation', 'comparison')),
    result_uri TEXT NOT NULL,
    trace_uri TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS external_run_link_one_derivation_idx
    ON external_run_link (plan_version_id)
    WHERE link_role = 'derivation';

CREATE INDEX IF NOT EXISTS isolation_plan_created_at_idx
    ON isolation_plan (created_at DESC, plan_id DESC);

CREATE INDEX IF NOT EXISTS isolation_plan_state_created_idx
    ON isolation_plan (lifecycle_state, created_at DESC, plan_id DESC);

CREATE INDEX IF NOT EXISTS plan_version_plan_version_no_idx
    ON plan_version (plan_id, version_no DESC);

CREATE INDEX IF NOT EXISTS isolation_runs_planning_context_idx
    ON isolation_runs (
        equipment_tag,
        (request->>'cnvrt_project_id'),
        (request->>'collection_id'),
        (request->>'job_id'),
        (request->>'unigraph_project_id')
    );
