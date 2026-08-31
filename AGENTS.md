# Equipment Isolation Runner — Agent Instructions

## Quick Start

```bash
uv sync  # installs deps to .venv/

# Run isolation for equipment (deterministic baseline, no LLM)
uv run equipment-isolation --equipment BT-11 --job-name pnid_2_bio_final --job-id 2100

# Run the AGENTIC (Gemini-orchestrated) isolation runner
uv run equipment-isolation-agent --equipment BT-11 --job-name pnid_2_bio_final --job-id 2100

# Run the HTTP API for CNVRT integration
uv run equipment-isolation-api

# List available equipment from JanusGraph
uv run equipment-isolation --list-equipment

# Run unit tests (stdlib unittest — pytest is NOT installed)
uv run python -m unittest discover -s tests

# Run a single test module
uv run python -m unittest tests.test_isolation_policy

# Compare agent vs deterministic baseline across equipment
uv run equipment-isolation-eval BT-11 C-02
```

## Environment

- Python 3.11 managed by `uv`; key dependencies in `pyproject.toml` include
  `gremlinpython`, `requests`, `google-genai`, FastAPI, SQLAlchemy, Alembic,
  and the psycopg PostgreSQL driver.
- Virtual env at `.venv/` (created by `uv sync`)
- `.env` is git-ignored; copy `.env.example` → `.env` and set `PLANT360_AUTH_TOKEN`, `GEMINI_API_KEY`, and optionally `GEMINI_MODEL`, `JANUSGRAPH_URL` / `JANUSGRAPH_USERNAME` / `JANUSGRAPH_PASSWORD`
- API persistence requires Postgres via separate `.env` fields:
  `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`,
  `POSTGRES_PASSWORD`, `POSTGRES_SSLMODE`. Alembic migrations are the
  authoritative schema source; run `uv run alembic upgrade head` before startup.
- `GEMINI_API_KEY` is required by the agentic runner (`equipment-isolation-agent`); the deterministic runner does not need it
- `.env` is loaded by `equipment_isolation.pipeline.env.load_dotenv` — not python-dotenv

## Key Commands

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Run isolation (deterministic) | `uv run equipment-isolation --equipment <TAG> [--job-name <NAME>] [--job-id <ID>]` |
| Run isolation (agentic / Gemini) | `uv run equipment-isolation-agent --equipment <TAG> [--model gemini-2.5-flash] [--max-steps 16]` |
| Run API service | `uv run equipment-isolation-api` |
| Apply database migrations | `uv run alembic upgrade head` |
| Show database revision | `uv run alembic current` |
| Show migration head | `uv run alembic heads` |
| Check ORM/schema drift | `uv run alembic check` |
| Create migration | `uv run alembic revision --autogenerate -m "<description>"` |
| Preview upgrade SQL | `uv run alembic upgrade head --sql` |
| Verify ORM on disposable PostgreSQL | `uv run python scripts/verify_postgres_orm.py` |
| Verify installed-wheel resources | `uv build --wheel && uv run python scripts/verify_wheel.py dist/equipment_isolation-*.whl` |
| List equipment | `uv run equipment-isolation --list-equipment [--equipment-limit N]` |
| Run tests | `uv run python -m unittest discover -s tests` |
| Eval agent vs baseline | `uv run equipment-isolation-eval <TAG>...` (or `--limit N`) |
| API auth | `PLANT360_AUTH_TOKEN=xxx` env or `--auth-token xxx` |
| Project context | Edit `project_config.json` or `--project-profile <NAME>` |
| Custom graph host/source | `--host <IP> --port <PORT> --project-id <UNIGRAPH_ID>`; traversal source defaults to `graph<UNIGRAPH_ID>_traversal` |
| Override output dir | `--output-dir /path/to/dir` |
| Quiet mode | `--quiet` |

## Database Migration Workflow

- Alembic migrations under `equipment_isolation/api/migrations/versions/` are the authoritative
  schema history. The root `alembic.ini` supports repository CLI commands;
  runtime migration-head checks load the application-owned migration package
  through `importlib.resources`. SQLAlchemy models in `equipment_isolation/api/db_models.py` define
  the current runtime schema and stay internal to the repository layer.
- After changing ORM metadata, run
  `uv run alembic revision --autogenerate -m "<description>"`, then explicitly
  review and complete both `upgrade()` and `downgrade()`.
- Autogenerate is a proposal, not approval. Renames, data backfills, standalone
  sequences, JSONB expressions, partial indexes, PostgreSQL-specific changes,
  and destructive operations require deliberate migration edits and review.
- Run `uv run alembic check` to detect ORM/database drift. Never use
  `Base.metadata.create_all()` in application startup or deployment.
- Before applying a new revision, inspect `uv run alembic history --verbose`
  and preview SQL with `uv run alembic upgrade head --sql` when practical.
- Apply migrations as a deployment step with `uv run alembic upgrade head`.
  Verify both `uv run alembic current` and `uv run alembic heads` report the
  same head before starting the API.
- The API must never apply DDL on startup. Startup should fail clearly when the
  database is missing, incomplete, unversioned, or behind the packaged head.
- A fresh database must run `upgrade head`. Use `stamp` only to adopt an
  existing database after its schema is verified to match the stamped revision.
- Treat downgrades and database recreation as destructive. Preserve immutable
  runs/plans with a verified backup when their data matters, resolve the exact
  database name first, and never reset a shared or production database as part
  of routine development.
- After a migration, run backend tests, `git diff --check`, and `git status`.
  For non-trivial DDL, also migrate a disposable PostgreSQL database and exercise
  repository readiness and affected persistence operations.

## Architecture

```
equipment_isolation/
├── runner.py        deterministic 15-stage runner
├── evaluation.py    agent-versus-baseline harness
├── config.py        GraphConfig, ApiConfig, IsolationPolicy, WorkScope, RunConfig
├── core/            boundary, candidates, evidence, obligations, LOTO, validation
├── integrations/    JanusGraph, UniGraph, HILT, STLM, CNVRT, image/job clients
├── presentation/    bbox resolution, payload construction, overlays, viewer
├── domain/          shared enums, models, classification, identity, feedback
├── pipeline/        shared config builder, metadata stages, equipment listing
├── agent/           Gemini orchestration, tools, session, OSHA reference
└── api/             FastAPI routes, PostgreSQL repository, packaged migrations
```

API design rule: `equipment_isolation.api` must call
`equipment_isolation.pipeline.config_builder.build_run_config` and
`equipment_isolation.agent.runner.run_agent_pipeline`; it must not assemble its own `RunConfig`
or duplicate the agent post-run payload merge.

API requests must supply project context explicitly: `cnvrt_project_id`,
`collection_id`, and `unigraph_project_id`. The API must not rely on
`project_config.json` / `active_profile`; those are CLI/dev conveniences only.

### Agentic design (`equipment_isolation.agent`)

The LLM is the **orchestrator**: it runs a tool-calling loop and decides which
deterministic stage to call next. The deterministic modules are preserved
UNCHANGED and exposed as tools. The deterministic `validate()` is the
AUTHORITATIVE source of `assurance_status`; the agent may gather more evidence
but cannot declare isolation on its own. For LOTO sequencing, the deterministic
`loto.py` produces the AUTHORITATIVE OSHA 1910.147(d) 6-phase order; the agent
uses `get_osha_guidance` (RAG) to reason about within-phase ordering and cite
provisions, but cannot reorder or skip phases. Nozzle->valve connectivity is
resolved AUTHORITATIVELY by `hilt_topology.py` and merged in `bbox.py`,
overriding JanusGraph depth+bbox picks. Heavy pipeline data stays server-side in
`AgentSession`; tools return compact summaries to keep Gemini's context small.
Every tool call is recorded in an audit trace (`<TAG>_trace.json`).

Available agent tools: `fetch_boundary`, `find_candidates`, `resolve_bboxes`,
`analyze_isolation_obligations`, `analyze_isolation_schemes_and_relief`,
`list_unselected_sources`, `investigate_source`, `build_evidence`,
`analyze_instrument_context`, `validate`, `get_osha_guidance`,
`build_loto_procedure`, `set_isolation_order`, `analyze_downstream_impact`,
`finalize_plan`.

## Pipeline Steps (`equipment_isolation.runner`)

15 deterministic stages: (1) resolve Unigraph project metadata, (2) fetch
boundary from JanusGraph + resolve job, (3) select candidates, (4) resolve
bboxes from STLM/HILT, (5) isolation obligations, (6) isolation schemes +
relief, (7) instrument context, (8) evidence classification, (9) plan evidence
checks, (10) validate assurance, (11) downstream impact, (12) LOTO procedure,
(13) build final JSON payload, (14) download P&ID image, (15) write JSON +
HTML viewer.

## Configuration Notes

- Project context defaults from `project_config.json`; active profile is `aker_277` (`cnvrt_project_id=277`, `collection_id=206`, Unigraph `project_id=15`, traversal source `graph15_traversal`, host `44.217.77.13:18182`)
- Use `--project-profile biodiesel_graph9` to run the older biodiesel/FT-18 context
- API base URL: `https://api.plant360.ai:8080`; Unigraph metadata API base: `https://api.plant360.ai/plantgraph`
- Fallback `JOB_IDS_BY_NAME` lives in `equipment_isolation/config.py` (pnid_1_bio_final=2099, pnid_2_bio_final=2100, etc.)
- Default output dir: `output/` (deterministic), `output_agent/` (agentic), repo-relative and git-ignored
- Agent default model: `gemini-2.5-flash` (override via `GEMINI_MODEL` env or `--model`)
- The API writes no local run files; PostgreSQL is authoritative for run and plan state
- API requests should pass the Plant360 token with `Authorization: Bearer ...`.
  For local/dev only, the API falls back to server-side `PLANT360_AUTH_TOKEN`
  when no request token is supplied.
- `POSTGRES_HOST`, `POSTGRES_DB`, and `POSTGRES_USER` are required by the API.
  Run request/status/result/trace/events and saved plans live only in PostgreSQL;
  startup fails when PostgreSQL is unavailable or is not at the packaged Alembic
  migration head. The API never applies DDL on startup. Drawing/HILT content is
  proxied from CNVRT, not retained locally.
- Isolation policy: UniGraph fallback uses cycle-safe adaptive branch traversal and stops each path at its first available eligible barrier or a terminal. `max_traversal_depth=20` is only a fail-safe ceiling; reaching it leaves the path unresolved. Eligible classes = valves/blinds/flanges/breakers/disconnects; conditional classes (check/control/undefined valve) are selected but flagged manual-review.
- Work scope defaults: intrusive=true, high_risk_service=true → requires positive isolation

## Output Files

Deterministic: `<TAG>.json` (final UI payload) + `<TAG>.html` (bbox overlay viewer).
Agentic: same two files plus `<TAG>_trace.json` (agent transcript + per-tool audit trace).
HTML viewer uses a blank canvas unless `--image-url` or the API image download succeeds.

## Gotchas

- **No lint/type-check/CI** — `tests/` has unit tests (run via `unittest`, NOT pytest); `equipment-isolation-eval` is the agent-vs-baseline regression check; no other automation
- **Tests are pure-logic** — they run offline in <1s and do NOT hit the graph or API
- **Graph connection required** to actually run the pipeline — JanusGraph must be reachable at configured host/port
- **API auth needed** for bboxes/P&ID image — without `PLANT360_AUTH_TOKEN`, bboxes stay empty
- **Agent fails fast without `GEMINI_API_KEY`**
- **Job inference** — if `--job-name` not provided, the runner infers it from candidate/boundary `unit_name` matching `job_ids_by_name`
- **Agent non-determinism** — `temperature=0` but LLM calls vary; the audit trace is the source of truth
- **Safety** — the agent is a POC decision-support aid, not a certified LOTO procedure; `validate()` is authoritative

## File Ownership

- All application code lives under the `equipment_isolation` package and uses
  package-qualified imports. Root Python files are compatibility launchers only.
- Deterministic logic belongs in `core/`, external systems in `integrations/`,
  and payload/viewer concerns in `presentation/`.
- Runtime persistence uses synchronous SQLAlchemy ORM sessions over the psycopg
  PostgreSQL driver. ORM entities must not leak into routes, Pydantic contracts,
  or deterministic safety-domain logic. Alembic owns schema history and every
  ORM schema change requires a reviewed migration.

## Unigraph Backend Reference

Local backend repo: `../../graph-convert` (Flask; route registration in `unigraph/api/routes.py`).
Key route for mapping CNVRT project/collection to Unigraph project metadata:
`GET /api/projects/by-cnvrt?cnvrt_project_id=<id>&cnvrt_collection_id=<id>` — the
preferred entry point over hardcoding `unigraph_project_id`.
