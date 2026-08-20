# Equipment Isolation Runner

Equipment isolation planner for LOTO (lock-out/tag-out). It resolves an
isolation boundary from graph traversal and Plant360 APIs, validates assurance
status, and builds an OSHA 1910.147(d) LOTO procedure.

Two runners share the same deterministic domain modules:

- **Deterministic runner (`run.py`)** — no LLM calls; pure graph traversal + APIs.
- **Agentic runner (`agent/`)** — a Gemini LLM orchestrates the same deterministic
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
uv run python -m run --equipment BT-11 --job-name pnid_2_bio_final --job-id 2100
```

List available equipment tags from JanusGraph:

```bash
uv run python -m run --list-equipment
```

The list includes graph id, tag, name, entity class, job id, and PNID/job name
when the equipment can be matched to STLM data. Limit it for quick browsing:

```bash
uv run python -m run --list-equipment --equipment-limit 20
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
run.py            CLI entrypoint, orchestrates the deterministic pipeline
config.py         Runtime config dataclasses
graph_client.py   Gremlin connection and vertex helpers
boundary.py       Equipment/nozzle boundary traversal
candidates.py     Deterministic isolation candidate selection
bbox.py           STLM bbox resolver (merges AUTHORITATIVE HILT topology picks)
hilt_topology.py  HILT nozzle<->valve connectivity resolver (AUTHORITATIVE)
obligations.py    Process/isolation obligation analysis
relief.py         Isolation scheme + relief-point detection
impact.py         Downstream impact analysis
instrument_context.py  Instrument context classification (advisory only)
evidence.py       Evidence classification
planner.py        Deterministic evidence-check rules
validator.py      Assurance status validator (AUTHORITATIVE)
loto.py           OSHA 1910.147(d) LOTO procedure sequencer
output.py         UI payload and HTML overlay writer
viewer.py         HTML overlay renderer
image.py          P&ID image download
domain/           Shared domain types: enums, models, classification, serialization
```

## Agentic Runner (Gemini-orchestrated)

The `agent/` package adds a runner where a Gemini LLM is the **orchestrator**. It
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
uv run python -m agent --equipment BT-11 --job-name pnid_2_bio_final --job-id 2100
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

Apply the repository schema and verify the required tables:

```bash
PGPASSWORD='replace-with-a-strong-password' \
  psql -h localhost -U eqiso_app -d eqiso -f schema.sql

PGPASSWORD='replace-with-a-strong-password' \
  psql -h localhost -U eqiso_app -d eqiso -c '\\dt'
```

If PostgreSQL and an authorized role already exist, the shorter setup is:

```bash
createdb eqiso
psql -d eqiso -f schema.sql
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

For a remote or differently named database, pass the equivalent `-h`, `-p`,
`-U`, and `-d` arguments to `psql`. `schema.sql` is the development/bootstrap
schema source. Set `EIA_AUTO_INIT_SCHEMA_ON_STARTUP=true` only when this process
is explicitly responsible for applying it; the recommended default is `false`.
Production schema changes should be applied in a controlled deployment step.

Optional connection-pool settings are `POSTGRES_POOL_MAX_SIZE` (default `8`) and
`POSTGRES_POOL_TIMEOUT_SECONDS` (default `5`).

### Start the API

```bash
uv run python -m api
```

By default, the server listens on `0.0.0.0:8088`. Override with `EIA_HOST` and
`EIA_PORT`. Startup fails if PostgreSQL is unconfigured, unreachable, or does
not contain the complete schema.

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
```

`POST /isolation-plans/from-run` idempotently promotes a succeeded persisted run
to an immutable advisory draft (`isolation_plan` + version 1 + run link). The
latest draft is not active or authorised, and reopening it does not invoke the
agent.

PostgreSQL is the API's sole persistence layer for run requests, status, events,
results, traces, plans, and versions. The API writes no local run files. Drawing
images and HILT content are served through authenticated CNVRT proxy endpoints
rather than retained as run artifacts.

### Start the frontend

The frontend requires Node.js, `pnpm`, and a `GITHUB_PACKAGES_TOKEN` with
`read:packages` access to the private `@coditation-cnvrt/p360-hitl-viewer`
package.

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

Populate `frontend/.env.local` with the approved CNVRT password-grant client
configuration and API URL:

```dotenv
VITE_API_BASE_URL=http://localhost:8088
VITE_APP_SERVER_BASE_URL=https://api.plant360.ai:8080
VITE_APP_OAUTH_CLIENT_ID=<approved-client-id>
VITE_APP_OAUTH_CLIENT_SECRET=<approved-client-secret>
```

Never commit tokens or populated credential files. Browser requests authenticate
through CNVRT and send the resulting bearer token to this API. See
[`frontend/README.md`](frontend/README.md) for frontend-specific details.

## Tests

Pure-logic unit tests run offline (no graph/API) via stdlib `unittest`:

```bash
uv run python -m unittest discover -s tests       # all tests
uv run python -m unittest tests.test_relief       # a single module
```

Compare the agent against the deterministic baseline across equipment:

```bash
uv run python eval_compare.py BT-11 C-02
```
