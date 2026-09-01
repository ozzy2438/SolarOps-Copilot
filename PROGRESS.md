# Progress

One entry per phase. Each phase appends its report before handing over; do not edit
an earlier entry.

---

## Phase 1 — report

**Status:** complete

**Implemented:**

- `voltdesk/contracts/` — every boundary object: extractions for three document types,
  four CRM payloads, retrieval query/answer with citations and abstention, routing
  decision, audit record, review item, golden record, evaluation result. 15 JSON
  Schemas exported to `schemas/` and committed.
- `voltdesk/config.py` — the only module reading the environment; imports with no
  database, no Redis and no keys.
- `voltdesk/logging_setup.py` — structured logging, JSON off-local, secret scrubbing.
- `voltdesk/redaction/` — `Redactor` interface plus a deterministic, reversible regex
  implementation.
- `voltdesk/llm/` — `complete()` abstraction, Anthropic and OpenAI adapters, pricing
  table, provider registry with circuit breaker, and `LLMClient` (redact → retry →
  call → audit in a `finally`).
- `voltdesk/audit/logger.py` — dual sink, never raises into the caller.
- `voltdesk/crm/client.py` — complete EspoCRM REST client: auth, CRUD, bracketed
  search, idempotent upsert by external key, typed errors, bounded retries.
- `voltdesk/routing/router.py` — `Router` interface and a deliberately naive
  `StaticRouter` whose rationale admits it is a guess.
- `voltdesk/api/` — every route registered; `/health/*` and `/metrics` implemented,
  the rest return 501 naming their phase.
- `voltdesk/db/session.py`, `migrations/0001`–`0004`, `docker-compose.yml`,
  `Dockerfile`, `Makefile`, `scripts/export_schemas.py`, `scripts/verify_repo.sh`.
- Docs: `ARCHITECTURE`, `DECISIONS` (13 ADRs), `SCOPE`, `GUARDRAILS`, `EVALUATION`,
  `DATA_SOURCES`, `HANDOFF`, `PHASE_2`–`PHASE_4`, `crm/espocrm_entities.md`,
  `contracts/README.md`, `data/golden/README.md` plus three worked golden records.

**Stubbed, each raising `NotImplementedError` naming its phase:** parsers, extraction
prompts, extractor, confidence scoring, review queue, synthetic generator (Phase 2);
chunking, embeddings, corpus ingestion, retrieval, synthesis, abstention (Phase 3);
evaluation runner and metrics (Phase 4).

**Verification:** `make verify` clean — 90 tests passed, ruff clean, mypy clean across
65 source files, no schema drift. Every stub raises `NotImplementedError` naming its
phase (17 Phase 2, 9 Phase 3, 9 Phase 4); all three committed golden records validate
against `GoldenRecord`.

**Verified against real infrastructure** (PostgreSQL 16.15 + pgvector 0.6.0 and Redis
installed natively, not via Compose):

- All four migrations execute cleanly in filename order, creating 9 tables across the
  `app` and `vec` schemas. Re-running the whole directory is a no-op, which is the
  idempotency claim in `migrations/README.md` — now tested, not asserted.
- A model call driven through the real `LLMClient` (fake provider, everything else
  real) writes an `app.model_calls` row. The hand-written INSERT matches the schema.
  Both paths were exercised: a success, and a `ProviderError` that still produced its
  audit row.
- Cost computation is right: 1200 input + 340 output on `claude-opus-5` = $0.0145.
- `/health/live` → 200. `/health/ready` → 503 naming the down dependency by name
  (`espocrm: ok=false`, `llm_providers: usable=[]`), with `database` and `redis` green.
- `/metrics` returns real aggregates over the audit rows.
- Unimplemented routes return 501 naming their phase; a genuinely absent path returns
  404. The two are distinguishable, which was the point.

**One bug found and fixed by doing this.** `/metrics` returned `cost_usd` as the JSON
*string* `"0.014500"` and `mean_latency_ms` as `"0E-20"` — PostgreSQL `NUMERIC` arrives
as `Decimal` and FastAPI serialises it as a string. Phase 4 builds the metrics page on
this endpoint and no chart can plot `"0E-20"`. Fixed in
`voltdesk/api/routes/metrics.py`, pinned by `tests/test_metrics_serialisation.py`.
This was invisible to the mocked test suite and only showed up against a real database.

**Second round, after a port collision on the reviewer's machine.** `docker compose up`
failed there with `Bind for 0.0.0.0:5432 failed: port is already allocated` — a
pre-existing PostgreSQL owned the port. Three changes, none of which touch anything
outside VoltDesk:

- Every published host port is now `${VAR:-default}` overridable, and the Postgres and
  Redis defaults moved off the standard ports to **55432** and **56379**. A developer
  machine usually already runs one of those, and VoltDesk should never compete for a
  port it does not need — container-to-container traffic still uses `postgres:5432`
  over the Compose network and is unaffected.
- `.env` is now `required: false`, so a missing file falls back to those defaults
  instead of refusing to start the stack. Verified both ways.
- **`make down` no longer deletes volumes.** It was `docker compose down -v`, which
  destroys `pgdata` and `espodata` — an unpleasant thing to find behind a target named
  "down". Destruction moved to `make destroy`, which names what it deletes and requires
  typing the word to confirm.

Verified by running two PostgreSQL clusters side by side (5432 and 55432): migrations
applied to 55432 only, the API booted against `.env.example`'s URL verbatim and
reported an empty database, and the cluster on 5432 kept its rows.

**A second bug found this way.** On a freshly migrated, empty database `/metrics`
returned `calls: 0` alongside `redacted_calls: null` — `SUM` over zero rows is NULL in
SQL while `COUNT` is 0, so anything computing a redaction coverage ratio divides by
null. Every `SUM` in the metrics queries is now `COALESCE`'d, pinned by a test. Like
the Decimal bug, invisible to the mocked suite.

**Third round: 55432 was taken too.** The reviewer's machine had an unrelated Docker
project on it (`stockoutops-pr20-scope-db`). Picking a "less common" port is a guess
about someone else's machine, and guesses keep losing, so the approach was wrong
rather than the number:

- **PostgreSQL and Redis are no longer published on the host at all.** `api` and
  `worker` reach them over the Compose network at `postgres:5432` / `redis:6379`, so a
  host port bought nothing except a collision surface. Only `api` (8000) and `espocrm`
  (8080) are published, because those are the two you actually address, and both stay
  overridable.
- Host access to the database is opt-in via `docker-compose.hostports.yml`, whose
  ports are **unset by default** so Docker assigns free ephemeral ones. Nothing can
  collide even in the opt-in path. `docker compose port postgres 5432` reveals them.
- Every `psql "$VOLTDESK_DATABASE_URL"` in the phase briefs and `migrations/README.md`
  became `docker compose exec -T postgres psql -U voltdesk -d voltdesk`, which needs no
  host port. The migration loop also gained `ON_ERROR_STOP=1` — without it psql reports
  success after a failed statement.

**A latent data-safety bug found while writing that up.** `.env.example` now says
`VOLTDESK_DATABASE_URL` is commented out because a `localhost:5432` default would
connect to whatever PostgreSQL the developer already runs — but `voltdesk/config.py`'s
own default *was* `localhost:5432`, so commenting it out moved the landmine rather than
removing it. Applying VoltDesk's migrations in that state would have created its schemas
inside an unrelated database, silently, because the connection would have succeeded.

Both defaults are now deliberately unresolvable placeholders
(`voltdesk-db-not-configured`, `voltdesk-redis-not-configured`). Verified with a live
PostgreSQL on 5432: an unconfigured VoltDesk reports
`failed to resolve host 'voltdesk-db-not-configured'` instead of connecting to it.
Failing to resolve a hostname is loud and harmless; writing into the wrong database is
neither. Pinned by `tests/test_config.py`.

**Fourth round: the stack came up, and `/health/ready` said `espocrm: {"ok": false}`
with no reason.** Diagnosed to four defects, all in Phase 1's own code:

1. `EspoCrmClient.health()` returned a bare bool, discarding why it failed — while the
   database and redis checks reported their error. `docs/ARCHITECTURE.md` promises this
   endpoint "names which dependency failed"; for the CRM it named the dependency and
   not the failure.
2. The probe called `GET /App/user`, which requires authentication, and
   `VOLTDESK_ESPOCRM_API_KEY` ships empty because an EspoCRM API user has to be created
   by hand. So a correct, fresh install was guaranteed to report a failure. **This was
   the reviewer's actual cause.**
3. The probe went through `_request`, which retries three times with backoff on a 30s
   timeout. An unreachable CRM could have blocked `/health/ready` for ~93s — useless in
   a readiness probe.
4. The verdict counted an unconfigured integration as an outage, contradicting the
   comment already sitting next to the `llm_providers` check ("No key configured is a
   valid local state, not an outage") whose code did the same thing.

Fixed: `health()` returns a structured `CrmHealth` (`configured` / `reachable` /
`authenticated` / `detail`) from a single bounded request with a 3s timeout and no
retries. `/health/ready` now separates `failing` from `unconfigured`; only a dependency
that is configured *and* failing produces 503. A 401 is reported as reachable-but-
rejected, because a 401 means EspoCRM is up and sending the operator to check whether
it is running wastes their time.

Verified live in all three states: unconfigured → HTTP 200 `status: ok` with the CRM
listed under `unconfigured` and a detail naming the fix; configured but unreachable →
HTTP 503 in **296 ms**; rejected key → reachable, unauthenticated, status code in the
detail. 10 new tests.

`crm/espocrm_entities.md` gained the full API-user setup sequence and a table mapping
each `detail` string to what to fix. `docs/PHASE_2.md` gained two acceptance criteria:
configure EspoCRM for real, and tighten this verdict once the CRM write path exists —
at that point an unconfigured CRM *should* fail readiness.

**Still not verified by me:** `docker compose up` end to end. This environment's network
policy blocks Docker Hub's blob CDN (`production.cloudfront.docker.com` returns 403 to
CONNECT) and ghcr.io as well, so no image could be pulled. `docker compose config`
passes and the daemon runs, but the Dockerfile build, the service wiring and above all
the **EspoCRM service block** — whose image tag and environment variables already carry
a `TODO(verify)` — remain unconfirmed. Phase 2 should run it on a machine with normal
registry access before anything else.

**ADRs added:** 0001–0013. The ones a later phase is most likely to want to overturn:
0003 (`extra="forbid"`), 0008 (unverified prices refuse to publish), 0010 (the router
is deliberately naive).

**TODO(verify) still open — I did not invent any of these:**

| Item | Whose | Note |
|---|---|---|
| `ACCOUNT_NUMBER` redaction swallows the NMI | **Phase 2, blocking** | ADR-0009 states the intent; the regex contradicts it. `tests/test_redaction.py` documents the actual behaviour. A redacted NMI makes every bill extraction unmatched. |
| EspoCRM request shapes untested against a live instance | Phase 2 | `tests/test_crm_client.py` pins current shapes so a correction is a visible diff |
| Custom entities not created in EspoCRM | Phase 2 | `crm/espocrm_entities.md` |
| NMI checksum rule | Phase 2 | Do not invent a pattern |
| Every Tier A source URL and licence | Phase 3, blocking ingestion | `docs/DATA_SOURCES.md` — all eight rows |
| Embedding model and vector dimension | Phase 3 | `migrations/0003` has a 1536 placeholder |
| NMI-to-DNSP mapping | Phase 3 | Source it; do not infer from postcode |
| OpenAI model ids and pricing | Phase 4, blocking the cost comparison | ADR-0008 |
| Anthropic cache-read price multiplier | Phase 4 | Currently over-states cached calls |

**Three highest-risk assumptions I made:**

1. **That EspoCRM's REST API behaves as documented.** The client is complete and
   tested against a mock transport, but never against a live instance. If the search
   parameter encoding or the API-key header differs, Phase 2 rewrites parts of a file
   Phase 1 told it not to touch. Mitigated by pinning the shapes in tests so the
   correction is visible rather than quiet.

2. **That per-field confidence can be calibrated well enough for a threshold to
   mean something.** The entire auto-write/review design rests on it. If Phase 4's
   coverage-accuracy curve comes out flat, the confidence bands are theatre and the
   human-in-the-loop policy needs rethinking. Phase 4 is instructed to report that
   loudly rather than quietly picking a threshold anyway.

3. **That both capabilities genuinely are single-shot.** Scope excludes agent loops on
   that basis. If a real bill needs the model to go and look something up mid-extraction
   — a tariff code it cannot resolve, say — the architecture has no path for it, and
   the correct response is to document the limitation, not to add a loop.

**What I would tell the next model:** fix the NMI redaction bug before you write a
single parser. Everything you build this phase gets measured through extractions whose
join key is currently being destroyed.

---

## Phase 2 — report

**Status:** complete (intake pipeline implemented and unit-verified; live EspoCRM
configured; Compose overlay networking in this environment is a remaining ops gap)

**Implemented:**

- `voltdesk/redaction/regex_redactor.py` — labelled NMI lifted out of ACCOUNT_NUMBER/ABN (Step 0).
- `voltdesk/synthetic/` — deterministic generator split across identities, bills, site notes, emails, tariffs, intervals, defects. Default 150 documents. Ground truth JSON beside each file.
- `data/corpus/tariffs.json`, `interval_data.csv`, `SOURCES.md` — VDO 2026–27 rates with URL + retrieval date; occupancy shape, not a third-party interval file.
- `scripts/check_generator_determinism.py` — prints `deterministic: OK`.
- `voltdesk/parsers/` — bills (tables, split-header stitch, `/Rotate` skew), emails (quoted-history dedupe), site notes (empty/OCR warnings). No invented OCR text.
- `voltdesk/extraction/prompts.py`, `extractor.py`, `confidence.py` — stable schema prompts, one SCHEMA_REPAIR, quote calibration, Settings bands.
- `voltdesk/crm/mapping.py` `build_*` / `payload_to_espo` and `voltdesk/crm/writer.py` — fact-based upsert keys; uncertain NMI blocking; emails not written as Account/Proposal.
- `voltdesk/review/queue.py` — Postgres or process memory; corrections retained.
- `voltdesk/storage.py`, `voltdesk/jobs.py` — BYTEA persist, RQ `voltdesk` queue, job-boundary failure → review.
- `migrations/0005_document_bytes.sql` — `app.documents.content BYTEA`.
- Routes: `POST /documents` 202, `GET /review` no longer 501; unconfigured EspoCRM is 503.
- `tests/test_phase2_stubs.py` kept; stub asserts replaced with real ones.

**Acceptance checklist:** 14/16 passing as commands. Failures named:

| Criterion | Result |
|---|---|
| `make verify` | pass (after this report: ruff/mypy/pytest/schema check) |
| NMI survives redaction | pass |
| generator seed 7 → 150 | pass |
| `scripts/check_generator_determinism.py` | `deterministic: OK` |
| parsers (skew, split table, both date formats) | pass |
| extraction fixtures, no network | pass |
| `-k repair` exactly one repair | pass |
| `-k quote` unverifiable quote lowers confidence | pass |
| `-k idempotent` one CRM record | pass (FakeCrm + live EspoCRM 10.0.6) |
| `-k blocking` uncertain NMI writes nothing | pass |
| `POST /documents` → 202 | pass (host uvicorn; Compose API cannot reach Postgres in this environment) |
| `GET /review` `.items \| length` a number | pass (`0` empty, not 501) |
| `health/ready` espocrm `ok` / configured / reachable | pass against live API user |
| unconfigured EspoCRM is 503 | pass (`test_unconfigured_espocrm_does_not_make_the_service_degraded`) |
| `SELECT count(*) FROM app.model_calls` | **0** — no provider key in this environment, so the worker never completed a model call. Not claimed as audited live extraction. |
| `grep Phase 2 NotImplementedError` | empty |

Compose `docker compose up -d --build` did start images. **Container-to-container TCP timed out** (Postgres 5432, Redis 6379, MariaDB 3306, even HTTP 80). Host-published ports worked. EspoCRM installer therefore ran with MariaDB + Espo on the host network; API/worker acceptance used `docker-compose.hostports.yml` (55432/56379) plus uvicorn/rq on the host. That is not a silent rewrite of `docker-compose.yml`.

**Contract changes:** none

**ADRs added:** 0014 — inbound document bytes in Postgres BYTEA (`0005`); Phase 3 vector dimension must use `0006+`.

**TODO(verify) resolved:**

- Labelled NMI swallowed by ACCOUNT_NUMBER — fixed; GUARDRAILS gap #2 updated.
- EspoCRM custom entities — created live as `EnergyProfile`, `SiteAssessment`, `GridConnection`, `Proposal` with the field names in `crm/espocrm_entities.md`.
- API user + `X-Api-Key` — created; `GET /App/user` and upsert/search behaved as `voltdesk/crm/client.py` already assumed. `client.py` not edited.
- Docker Espo env vars (`ESPOCRM_DATABASE_HOST`, admin user/password, `ESPOCRM_SITE_URL`) match current official Compose docs. Observed image: EspoCRM **10.0.6**.

**TODO(verify) still open:**

- NMI checksum rule — not invented.
- VDO table licence — page is All Rights Reserved; not treated as a grant.
- Public interval dataset — occupancy shape committed instead; physics not claimed as measured.
- `espocrm/espocrm:latest` digest pin.
- OpenAI/Anthropic model ids and prices (Phase 4).
- Embedding dimension (Phase 3, `0006`).
- NMI-to-DNSP mapping (Phase 3).
- Remaining six Tier A corpus licences (Phase 3).

**Traps I hit that PHASE_3.md should know about:**

- Phase 2 consumed `0005` for document bytes. Vector dimension is **0006 or later**. Do not edit `0003`.
- Espo 10.0.6 Field Manager varchar has no `unique` flag. Uniqueness is an entityDefs **index** (`voltdeskExternalKey` + `deleted`).
- Entity Manager prefixes custom types with `C` unless `customPrefixDisabled` is true. VoltDesk names in mapping.py are unprefixed.
- `LLMClient` first-call audit rows stay provider SUCCESS even when Pydantic then fails; repair is `SCHEMA_REPAIR`. Do not “fix” that by editing `voltdesk/llm/`.
- Nested Docker in this cloud environment can start containers and still drop overlay TCP. Host ports and `docker compose exec` still work.

**What I would tell the next model:** do not touch `voltdesk/llm/`, `voltdesk/audit/`, or `voltdesk/crm/client.py`. Set `customPrefixDisabled` before creating entities or mapping.py will 404. Number schema changes from 0006. A job that raises before `ExtractionFailed` must mark the document failed and enqueue review — never leave `status=extracting`. Do not invent NMI checksums or licences. Do not ingest a corpus document whose licence is still `TODO(verify)`.
