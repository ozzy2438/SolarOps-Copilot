# Handoff

You are one of three models finishing this project. You did not see the conversation
that produced Phase 1. Everything you need is in this repository — that was the
point of Phase 1.

Read this document, then your phase brief (`docs/PHASE_2.md`, `PHASE_3.md`, or
`PHASE_4.md`). You should not need to make an architectural decision. If you think
you do, you have found a gap in Phase 1's work: record it as an ADR in
`docs/DECISIONS.md`, make the smallest decision that unblocks you, and say so in your
phase report.

## Where things are

| Path | What |
|---|---|
| `voltdesk/contracts/` | Every object crossing a boundary. **Read `contracts/README.md` first.** |
| `schemas/` | JSON Schema exports, generated and committed. Never hand-edit. |
| `voltdesk/llm/` | Provider abstraction. Call models through `LLMClient`, never an adapter. |
| `voltdesk/crm/client.py` | EspoCRM client. Complete. You should not need to modify it. |
| `voltdesk/audit/` | Audit logger. Complete. |
| `voltdesk/redaction/` | PII redaction. Complete, with a known bug — see below. |
| `voltdesk/api/` | FastAPI. Every route registered; unimplemented ones return 501 naming their phase. |
| `migrations/` | Plain SQL, applied in filename order. Never edit a committed file. |
| `docs/` | Architecture, decisions, scope, guardrails, evaluation, data sources. |
| `tests/` | 75 tests. `test_phase{2,3,4}_stubs.py` is the executable version of this document. |

## What exists and works

- Contracts for every boundary object, with committed JSON Schema exports.
- Configuration, structured logging, the audit logger.
- PII redaction: deterministic, reversible, with a working regex implementation.
- The LLM provider abstraction: one `complete()` interface, Anthropic and OpenAI
  adapters, a pricing table, a circuit breaker, retry, and a per-call audit record.
- The EspoCRM REST client, complete: auth, CRUD, search, idempotent upsert, typed
  errors, bounded retries.
- The FastAPI app with every route registered; `/health/*` and `/metrics` work.
- Migrations for documents, extractions, review queue, corpus, vectors, audit log,
  evaluation runs, incidents.
- Docker Compose for the whole stack.

## What does not exist

Every stub raises `NotImplementedError` with a message naming the phase that owns it.
Grep for it:

```bash
grep -rn --include="*.py" -A1 "raise NotImplementedError" voltdesk/ | grep -o "Phase [234]" | sort | uniq -c
```

- **Phase 2** — parsers, extraction prompts, the extractor, confidence calibration,
  the CRM write path, the review queue, the synthetic generator.
- **Phase 3** — corpus ingestion, chunking, embeddings, retrieval, citation-grounded
  synthesis, the abstention scorer.
- **Phase 4** — golden set execution, the Claude vs GPT benchmark, the real router,
  guardrails hardening, the metrics page, the daily batch, the incident log.

## Invariants you must never break

1. **Contracts: add fields, never rename or remove.** Phase 4 reads rows Phase 2 and 3
   wrote and cannot re-run them. A renamed field produces `None` in aggregation and
   wrong numbers with nothing raising. `voltdesk/contracts/README.md` has the detail.

2. **Never call a provider adapter directly.** `LLMClient.complete()` is the only
   supported path. It redacts, retries, breaks the circuit, and writes the audit
   record. Bypassing it produces an unaudited, un-redacted call.

3. **Every model call is audited, including failures.** The audit write is in a
   `finally` block. Do not move it.

4. **Never edit a committed migration.** Add a new numbered file.

5. **Never hand-edit `schemas/`.** Run `make schemas`. `--check` runs in `make verify`.

6. **Respect `docs/SCOPE.md`.** If your phase seems to need something on the
   out-of-scope list, document the limitation instead. That is a finding, not a
   failure.

7. **Never invent an external fact.** If you do not know an API's response shape, a
   source's licence, or a provider's price, write `TODO(verify)` and say so in your
   report. Phase 1 left several of these open on purpose — see below. Inventing a
   plausible detail is the worst available failure, because the next phase builds on it.

8. **Cost figures require verified prices.** Call
   `voltdesk.llm.pricing.assert_verified()` before publishing any cost number.
   OpenAI's prices are Phase 1 placeholders (ADR-0008).

## Verifying the repo is healthy

```bash
make install     # pip install -e ".[dev]"
make verify      # lint + typecheck + tests + schema drift check
```

or directly:

```bash
./scripts/verify_repo.sh
```

Expected on a clean Phase 1 checkout: **75 passed**, ruff clean, mypy clean, schemas
up to date. The stack:

```bash
docker compose up -d --build
curl -s localhost:8000/health/live     # {"status":"ok"}
curl -s localhost:8000/health/ready    # names any dependency that is down
```

## Open TODO(verify) items you inherit

Phase 1 refused to invent these. They are real work, not decoration:

```bash
grep -rn "TODO(verify)" --include="*.py" --include="*.md" --include="*.sql" . | wc -l
```

The ones that will bite:

| Item | Where | Whose |
|---|---|---|
| **`ACCOUNT_NUMBER` redaction swallows the NMI** | `voltdesk/redaction/regex_redactor.py`, ADR-0009 | **Phase 2, blocking.** A redacted NMI makes every bill extraction unmatched and will dominate Phase 4's numbers. |
| EspoCRM request shapes not tested against a live instance | `voltdesk/crm/client.py` | Phase 2 |
| Custom entities not created in EspoCRM | `crm/espocrm_entities.md` | Phase 2 |
| NMI checksum rule | `voltdesk/contracts/documents.py` | Phase 2 — do not invent a pattern |
| Tier A source URLs and licences — all of them | `docs/DATA_SOURCES.md` | Phase 3, blocking ingestion |
| Embedding model and vector dimension | `migrations/0003_vectors.sql` | Phase 3 — record an ADR |
| NMI-to-DNSP mapping | `voltdesk/contracts/crm.py` | Phase 3 — source it, don't infer from postcode |
| OpenAI model ids and pricing | `voltdesk/llm/pricing.py` | Phase 4, blocking the cost comparison |
| Anthropic cache-read price multiplier | `voltdesk/llm/pricing.py` | Phase 4 |

## How to know your phase is done

Your brief ends with an acceptance checklist where **every item is verifiable by
running a command**. Not "retrieval works" — a command, and what it should print.

You are done when the checklist passes and `make verify` is green. Then fill in the
report-back template at the end of your brief and commit it to `PROGRESS.md`, so the
next model inherits a status note instead of guessing.

## One last thing

The models after you are literal, and so are you. Prefer boring explicit code.
Keep files under ~300 lines. Give every module a docstring saying what it is for and
which phase owns it. Do not write code that needs a network call to succeed at import
time — the test suite runs with no network, no database and no API keys, and it must
stay that way.
