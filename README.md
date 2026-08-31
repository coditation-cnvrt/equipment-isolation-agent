# Equipment Isolation Runner

Equipment isolation planner for LOTO (lock-out/tag-out). It resolves an
isolation boundary from graph traversal and Plant360 APIs, validates assurance
status, and builds an OSHA 1910.147(d) LOTO procedure.

Two runners share the same deterministic application package:

- **Deterministic runner (`equipment_isolation.runner`)** — no LLM calls; pure graph traversal + APIs.
- **Agentic runner (`equipment_isolation.agent`)** — a Gemini LLM orchestrates the same deterministic
  stages as tools (see [Agentic Runner](#agentic-runner-gemini-orchestrated)).

> See `AGENTS.md` for the full command table, per-file architecture map, pipeline
> steps, and configuration notes.

## Setup

```bash
uv sync  # installs dependencies to .venv/
```

Copy `.env.example` → `.env`.

```bash
cp .env.example .env
```

For CLI runs, set `PLANT360_AUTH_TOKEN` when drawing images/bboxes are needed and
set `GEMINI_API_KEY` for the agentic runner. The deterministic runner does not
need Gemini or PostgreSQL. The HTTP API reads its trusted upstream service URLs
from `CNVRT_API_BASE_URL` and `UNIGRAPH_API_BASE_URL`, and its Gremlin connection
from `JANUSGRAPH_URL`; clients cannot override these connections per request.
The HTTP API and React application additionally require PostgreSQL as described
below.

## Run

```bash
uv run equipment-isolation --equipment BT-11 --job-name pnid_2_bio_final --job-id 2100
```

List available equipment tags from JanusGraph:

```bash
uv run equipment-isolation --list-equipment
```

The list includes graph id, tag, name, entity class, job id, and PNID/job name
when the equipment can be matched to STLM data. Limit it for quick browsing:

```bash
uv run equipment-isolation --list-equipment --equipment-limit 20
```

For bbox resolution, provide a Plant360 API token via `--auth-token` or the
`PLANT360_AUTH_TOKEN` environment variable. Without API auth, the runner still
returns graph candidates and assurance status, but bboxes remain empty.

## Outputs

Default output directory: `output/` (repo-relative, git-ignored)

```text
BT-11.json    final UI payload
BT-11.html    bbox overlay viewer
```

`BT-11.html` overlays resolved bboxes. Pass `--image-url` (or let the API image
download succeed) to render boxes over a P&ID image; otherwise the viewer uses a
blank canvas. Override the directory with `--output-dir`.

## Architecture

The deterministic runner executes a **15-step pipeline**: resolve Unigraph
project metadata → fetch boundary + resolve job → select candidates → resolve
bboxes → isolation obligations → schemes + relief → instrument context →
evidence classification → plan evidence checks → validate assurance → downstream
impact → LOTO procedure → build final payload → download P&ID image → write JSON
+ HTML viewer.

```text
equipment_isolation/
├── runner.py        deterministic 15-stage runner
├── config.py        runtime configuration dataclasses
├── core/            isolation selection, analysis, LOTO, and validation
├── integrations/    JanusGraph, UniGraph, HILT, STLM, and CNVRT clients
├── presentation/    payload, bbox, overlay, and viewer rendering
├── domain/          shared enums, models, identity, and feedback rules
├── pipeline/        shared configuration and pipeline orchestration
├── agent/           Gemini tool orchestrator over deterministic stages
└── api/             FastAPI service, persistence, and packaged migrations
```

The root `run.py`, `agent.py`, `api.py`, and `eval_compare.py` files are thin
compatibility launchers. Application code must import through
`equipment_isolation.*`.

## Agentic Runner (Gemini-orchestrated)

The `equipment_isolation.agent` package adds a runner where a Gemini LLM is the **orchestrator**. It
runs a tool-calling loop and decides which deterministic stage to call next. The
deterministic modules above are shared with the agent and exposed as tools; the
deterministic `validate()` remains the **authoritative** source of
`assurance_status` (the agent can gather more evidence but cannot declare
isolation on its own).

New results also include deterministic `plan_readiness`. This is deliberately
separate from assurance: `ready_for_field_review` means that planning blockers
are resolved and pre-job/field hold points are identified; it does **not** mean
that devices were operated, zero energy was demonstrated, or work is
authorized. Stored-energy release is ordered in LOTO phase 5 and zero-energy
verification in phase 6. Historical payloads are not assigned reconstructed
readiness states.

```bash
uv run equipment-isolation-agent --equipment BT-11 --job-name pnid_2_bio_final --job-id 2100
```

Agent tools: `fetch_boundary`, `find_candidates`, `resolve_bboxes`,
`analyze_isolation_obligations`, `analyze_isolation_schemes_and_relief`,
`list_unselected_sources`, `investigate_source`, `build_evidence`,
`analyze_instrument_context`, `validate`, `get_osha_guidance`,
`build_loto_procedure`, `set_isolation_order`, `analyze_downstream_impact`,
`finalize_plan`.

After `validate()`, the agent builds an **OSHA 1910.147(d) LOTO procedure**: the
6-phase order is fixed/authoritative (deterministic `loto.py`), and the agent
uses `get_osha_guidance` (RAG over the bundled OSHA 29 CFR 1910.147 reference) to
reason about within-phase device ordering and cite provisions. The procedure
(with field-action gaps for missing bleed/verification) is added to the output
payload as `loto_procedure`.

Outputs (default dir `output_agent/`):

```text
BT-11.json         final UI payload (same shape as the deterministic runner)
BT-11.html         bbox overlay viewer
BT-11_trace.json   agent transcript + per-tool audit trace
```

Requires `GEMINI_API_KEY` in `.env`. Default model `gemini-2.5-flash` (override
with `--model`). This is a POC decision-support aid, not a certified LOTO
procedure.

## HTTP API Server

### PostgreSQL setup

PostgreSQL is mandatory for the API. On Debian/Ubuntu, install and start it with:

```bash
sudo apt update
sudo apt install -y postgresql postgresql-client
sudo systemctl enable --now postgresql
```

Create a dedicated application role and database. Replace the example password
before running these commands:

```bash
sudo -u postgres psql -c "CREATE ROLE eqiso_app WITH LOGIN PASSWORD 'replace-with-a-strong-password';"
sudo -u postgres createdb --owner=eqiso_app eqiso
```

Configure `.env` for that database:

```dotenv
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=eqiso
POSTGRES_USER=eqiso_app
POSTGRES_PASSWORD=<the-strong-password-created-above>
POSTGRES_SSLMODE=prefer
```

Apply all Alembic migrations and verify the current revision:

```bash
uv run alembic upgrade head
uv run alembic current
```

If PostgreSQL and an authorized role already exist, create the application
database, configure `.env`, and then run the same Alembic commands.

Alembic reads the separate `POSTGRES_*` fields above; a database URL is not
required. Migrations are the authoritative schema source and must be applied in
a controlled deployment step before the API starts. The API never applies DDL
on startup and fails when the database is not at the packaged migration head.

The baseline revision, `0001_current_schema`, exactly represents the former
`schema.sql`. For an existing database that was created from that current schema
and has not drifted, adopt it once without replaying its `CREATE` statements:

```bash
uv run alembic stamp 0001_current_schema
uv run alembic current
```

Do not stamp a database with missing objects, local schema edits, or legacy
`isolation_runs.artifacts` / `isolation_runs.run_dir` columns. Reconcile such a
database explicitly before marking it as the baseline.

### Alembic cheat sheet

Alembic creates and orders revision files, records the applied revision, and
executes upgrades and downgrades. SQLAlchemy ORM metadata defines the current
application schema, while Alembic migrations remain its reviewed deployment
history. The API uses synchronous SQLAlchemy sessions internally and does not
expose ORM entities through its FastAPI/Pydantic contracts.

Inspect migration state:

```bash
uv run alembic current
uv run alembic heads
uv run alembic history --verbose
uv run alembic check
```

After editing ORM metadata, generate a candidate migration under
`equipment_isolation/api/migrations/versions/`, review both directions, and inspect the SQL before
applying it. The root `alembic.ini` is the CLI entry point; runtime startup
resolves the same application-owned migration package through Python package
resources, so installed wheels do not depend on a source checkout.

```bash
uv run alembic revision --autogenerate -m "add request schema versions"
uv run alembic upgrade head --sql
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

Autogenerate must always be reviewed. Renames, data backfills, standalone
sequences, JSONB expression indexes, partial indexes, destructive changes, and
other PostgreSQL-specific behavior commonly need explicit Alembic operations.
Never call `Base.metadata.create_all()` from application startup; every schema
change must have a committed migration. Run the backend tests and repository
checks after applying a migration:

```bash
uv run python -m unittest discover -s tests
git diff --check
git status --short
```

For a non-trivial persistence or migration change, run the disposable PostgreSQL
verification. It inspects the configured database, creates a uniquely named
sibling database, applies and reverses the migration, upgrades it again,
exercises the ORM repository and API lifespan, compares both catalogs, and
drops the disposable database:

```bash
uv run python scripts/verify_postgres_orm.py
```

For release packaging, build the wheel and run the isolated-layout verifier. It
checks that runtime modules, the OSHA and instrument resources, the Alembic
configuration/template/revisions, and migration-head discovery all work without
the repository on `sys.path`:

```bash
uv build --wheel
uv run python scripts/verify_wheel.py dist/equipment_isolation-*.whl
```

Downgrade one revision only when its data-loss implications have been reviewed:

```bash
uv run alembic downgrade -1
```

For a destructive local reset, first stop the API and back up any data that must
be retained. Then recreate exactly the configured development database:

```bash
pg_dump -U postgres --format=custom --file=eqiso-before-reset.dump eqiso
```

```sql
-- Run in: psql -U postgres
DROP DATABASE eqiso;
CREATE DATABASE eqiso OWNER eqiso_app;
\q
```

Recreate the complete schema and verify it:

```bash
uv sync
uv run alembic upgrade head
uv run alembic current
uv run alembic heads
psql -U postgres -d eqiso -c '\dt'
```

Both Alembic status commands should report the same revision with `(head)`.
Use `upgrade head`, not `stamp`, for a fresh database. `stamp` is reserved for
adopting an existing database whose schema has already been verified to match a
known revision.

Optional connection-pool settings are `POSTGRES_POOL_MAX_SIZE` (default `8`) and
`POSTGRES_POOL_TIMEOUT_SECONDS` (default `5`).

### Start the API

```bash
uv run equipment-isolation-api
```

By default, the server listens on `0.0.0.0:8088`. Override with `EIA_HOST` and
`EIA_PORT`. Startup fails if PostgreSQL is unconfigured, unreachable, or does
not match the packaged Alembic migration head.

API runs use the agentic runner, so `GEMINI_API_KEY` is required. Requests that
need Plant360 data must send `Authorization: Bearer <token>`; for local/dev only,
the service can fall back to `PLANT360_AUTH_TOKEN` from `.env`.

API requests must provide project context explicitly: `cnvrt_project_id`,
`collection_id`, and `unigraph_project_id`. The API does not use
`project_config.json` / `active_profile`.

Useful endpoints:

```text
GET  /health
POST /equipment
POST /isolation-runs
GET  /isolation-runs?equipment_tag=&job_id=&cnvrt_project_id=&collection_id=&unigraph_project_id=
GET  /isolation-runs/{run_id}
GET  /isolation-runs/{run_id}/events
GET  /isolation-runs/{run_id}/result
GET  /isolation-runs/{run_id}/trace
POST /isolation-plans/from-run
GET  /isolation-plans?equipment_tag=&job_id=&cnvrt_project_id=&collection_id=&unigraph_project_id=
GET  /isolation-plans/{plan_id}
GET  /isolation-plans/{plan_id}/versions/{version_id}
GET  /isolation-plans/{plan_id}/versions/{version_id}/diff
POST /isolation-plans/{plan_id}/changes
GET  /isolation-plans/{plan_id}/changes
POST /isolation-plans/{plan_id}/changes/{change_id}/approve
POST /isolation-plans/{plan_id}/derive
```

`POST /isolation-plans/from-run` idempotently promotes a succeeded persisted run
to an immutable, normalized advisory draft (`isolation_plan` + version 1 + run
link, scope, assets, branches, points, steps, findings, and input snapshots). The
latest draft is not active or authorised, and reopening it does not invoke the
agent.

Plan feedback never edits a version or its run result. A reviewer submits a typed
feedback record against the latest version, an authenticated reviewer approves it, and
`/derive` locks every outstanding approved change before launching a complete
child run. Advisory plans record audited self-approval; stricter plan modes
require separation of duties. Successful runs create the next immutable plan version;
failed runs remain in the parent-run tree and leave approved changes available
for retry. The diff endpoint compares the complete child projection with its
parent. See `docs/openapi.json` for the checked-in API contract.

Feedback is categorized as `input_correction`, `manual_observation`,
`requirement_deviation`, or `execution_failure`. The current advisory product
registers derivation handlers only for the first two categories; category/type
mismatches and unsupported future behaviors are rejected before they can reach
the deterministic pipeline. Existing `/changes` request and response names are
retained as a compatibility API. Review decisions are append-only, while the
feedback row retains approval fields as a query projection. See
`docs/feedback-architecture.md` for the category and persistence invariants.

Supported draft-review feedback actions are accepting or rejecting a conditional
manual-review candidate, confirming a bypass point, correcting a display label,
adding a graph-identified manual point, reporting an isolation point unavailable
(faulty, bypassed, or out of service), and returning a repaired point to service.
An unavailable device remains visible for audit but contributes no barrier or
LOTO action. HILT traversal continues through it to seek an alternate eligible
barrier; without one, the affected process branch becomes unresolved and
`validate()` reports that isolation is not demonstrated. Applied corrections are
replayed in later derivations until a later correction explicitly changes their
state. `validate()` remains authoritative.

PostgreSQL is the API's sole persistence layer for run requests, status, events,
results, traces, plans, and versions. The API writes no local run files. Drawing
images and HILT content are served through authenticated CNVRT proxy endpoints
rather than retained as run artifacts.

### Start the frontend

The React application is maintained separately in
[`coditation-cnvrt/equipment-isolation-agent-ui`](https://github.com/coditation-cnvrt/equipment-isolation-agent-ui).
It requires Node.js, `pnpm`, and a `GITHUB_PACKAGES_TOKEN` with `read:packages`
access to the private `@coditation-cnvrt/p360-hitl-viewer` package.

```bash
git clone https://github.com/coditation-cnvrt/equipment-isolation-agent-ui.git
cd equipment-isolation-agent-ui
cp .env.example .env.local
pnpm install
pnpm dev
```

Populate `.env.local` in the UI repository with the approved CNVRT
password-grant client configuration and API URL:

```dotenv
VITE_API_BASE_URL=http://localhost:8088
VITE_APP_SERVER_BASE_URL=https://api.plant360.ai:8080
VITE_APP_OAUTH_CLIENT_ID=<approved-client-id>
VITE_APP_OAUTH_CLIENT_SECRET=<approved-client-secret>
```

Never commit tokens or populated credential files. Browser requests authenticate
through CNVRT and send the resulting bearer token to this API. See the
[UI repository README](https://github.com/coditation-cnvrt/equipment-isolation-agent-ui#readme)
for frontend-specific details.

## Tests

Pure-logic unit tests run offline (no graph/API) via stdlib `unittest`:

```bash
uv run python -m unittest discover -s tests       # all tests
uv run python -m unittest tests.test_relief       # a single module
```

Compare the agent against the deterministic baseline across equipment:

```bash
uv run equipment-isolation-eval BT-11 C-02
```
