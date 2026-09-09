# Frontend FHR / SIC / PSD preview

Implemented 2026-09-08. This delivery makes the synthetic workflow testable through
React, authenticated FastAPI and PostgreSQL. It is **not completion of governed
production admission (B2), approved classification, or authoritative RBC solving**.
Those release gates in `fhr-implementation-plan.md` remain open.

## Try it

Open `http://localhost:5173/input-lab` and sign in with your CNVRT account. The
planning header also has a “FHR SIC PSD test workspace” action.

1. Load the stopped-equipment example. Inspect/edit FHR, SIC, PSD and synthetic
   HILT JSON; set explicit work scope and assessment time.
2. Select **Evaluate and save preview**. Review each path's fluid evidence,
   proposed HSC/EC, base RBC, device decisions, ordered topology and blockers.
3. Change personnel entry, duration, or a document; save a child preview. Inspect
   changed input hashes and added/removed/changed paths.
4. Reload the child or follow **Open preserved parent**. Parent content remains
   byte-preserved in persistence. Latest 50 previews are listed for the actor.
5. Try expired PSD, unknown service, unavailable first valve and cycle examples.
   Malformed JSON remains editable; invalid contracts produce a 422 field error.

The sample dates are intentionally fixed in September 2026 for reproducibility.
Selecting an expiry scenario changes assessment time rather than silently renewing
an Operations declaration. Sample HILT topology is invented, including explicit
per-link unit scopes, and is not the actual drawing 2151 connectivity.

## Implemented boundary

- `domain/planning_preview.py`: pure, bounded synthetic evaluation over captured
  HILT content, fluid resolution, proposed requirements 6.1/6.2 classification,
  base 16-cell matrix, duration positive-barrier escalation, limited device
  admissibility, and ordered path occurrences past the first barrier. No network,
  clock, LLM or production-run invocation occurs in this domain module.
- Highest-match classification and imported HSC override behavior are development
  proposals with approval blockers. PSD never reduces HSC. Unknown fluids,
  ambiguous services and missing conditions cannot become an isolation success.
- Graph traversal: at most 500 nodes/1000 links, depth 64, 2000 expansions. Dead
  ends, cycles, dangling endpoints and exhausted budgets remain explicit. Reaching
  a declared synthetic terminal does not establish real source completeness.
- Bleed location/safe destination, size/spec breaks, disconnection, field proving,
  source consistency and unresolved safety policy remain blockers. Actuated,
  check/control valves and unsupported devices never silently gain barrier value.
  No positive configuration verdict or `assurance_status` is assigned here.
- `api/planning_previews.py`: authenticated template/list/read/create endpoints;
  actor comes from CNVRT middleware. Ownership is checked on list/read/parent use.
  The source is public synthetic fixtures; this is not drawing authorization or
  controlled-document approval. Request documents must remain explicitly synthetic.
- Migration `0010_planning_previews`: separate immutable `planning_preview` table.
  Complete input/result/hash/parent/comparison commit together. Failed inserts
  leave no partial snapshot. Direct updates/deletes, different-owner parents, and
  non-synthetic/executable result inserts are rejected. Existing runs/plans/input
  hashes and A1/A2 manifests retain their meaning.
- Preview computation is synchronous and bounded, with no worker dispatch/recovery
  contract. Retrying a create can create a second immutable preview; it cannot
  mutate an existing one. Historical readback does not recompute against new code.
- B1 SIC composition supports an optional delta in the API. The UI edits the base
  SIC; there is no separately approved delta editor. Matrix overrides stay blocked.
- Packaged research fixtures under `equipment_isolation/fixtures` exactly match
  the researched docs, verified in tests. This packages examples, not production
  seeding. OpenAPI was regenerated; viewer package 0.2.0 is unchanged.

## Verification

- Backend: 487 tests passed including 20 opt-in PostgreSQL tests (four new preview
  tests). New coverage includes immutable parent/child history, actor isolation,
  direct SQL guards, atomic failure, HTTP round trips, scope/mode rejection,
  all matrix cells, threshold cases, input permutations, loops and budgets.
- UI: 80 tests, lint and build pass; five new workspace tests cover input editing,
  malformed JSON, child parent pins, server errors and cancellation.
- Fresh UTF-8 disposable database upgraded through 0010; ORM drift check passed.
  Upgrade from populated 0009 and downgrade/re-upgrade of the empty preview table
  were tested on the disposable cluster, never the configured database.
- Chromium browser against real CNVRT authentication and the running local
  FastAPI/PostgreSQL: create, derive, reload child, reopen unchanged parent passed;
  no page errors. Browser tooling was installed only under `/tmp`, not added as a
  project dependency. Credentials were not written to scripts or logs.

## Local services for this session

UI was already serving port 5173. API is running on 127.0.0.1:8088 with process-only
PostgreSQL overrides pointing to the **separate** `eia_test_preview_ui` database at
`/tmp/isolation-review-pg.zybHC2`, port 55439, user swarnim, SSL disabled. The cluster
and API are left running for frontend testing. Normal CNVRT authentication remains
active. Existing configured database and `.env` files were not migrated/edited;
the configured database was last observed at 0008.

The relocated virtual environment has a stale `uvicorn` launcher shebang. The
working startup invocation uses `uv run python -m uvicorn`:

```bash
POSTGRES_HOST=/tmp/isolation-review-pg.zybHC2 POSTGRES_PORT=55439 \
POSTGRES_DB=eia_test_preview_ui POSTGRES_USER=swarnim POSTGRES_PASSWORD='' \
POSTGRES_SSLMODE=disable EIA_CORS_ORIGINS=http://localhost:5173 \
uv run python -m uvicorn equipment_isolation.api.app:app --host 127.0.0.1 --port 8088
```

For another environment, use its intended development database and reviewed
Alembic upgrades; do not assume this temporary socket exists there.

## Still required for production

Follow B2 onward in the implementation plan: approved policy/identity/source
contracts; governed immutable graph/state capture and admission/dispatch; pinned
inputs throughout both runners; full configuration/bleed/fallback evaluation and
validator coverage; controlled revision freshness and production UI onboarding.
The synthetic preview must not become a shortcut around these gates. It is neither
a saved isolation plan nor a field procedure and cannot be promoted as one.
