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

**Verification:** `make verify` clean — 75 tests passed, ruff clean, mypy clean across
65 source files, no schema drift.

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
