# VoltDesk

An LLM service layer that sits alongside the CRM of a commercial solar and battery
installation company. It does two things and nothing else:

1. **Turns inbound documents into CRM records.** Electricity bills, site assessment
   notes and email threads become schema-validated structured records, written
   idempotently into EspoCRM — or held in a review queue when the system is not
   confident enough to write them unattended.
2. **Answers staff questions about the company's own technical and compliance
   knowledge**, with citations that can be checked, and an explicit refusal when the
   evidence is not there.

Around those two capabilities: task-level model routing between Anthropic Claude and
OpenAI GPT, an evaluation harness measuring accuracy / latency / cost per task, PII
redaction before any third-party call, and an audit row for every model call ever made.

> The repository is named `SolarOps-Copilot`; the system inside it is VoltDesk
> (ADR-0001).

## Status

**Phases 1–4 complete.** Document intake/extraction, cited knowledge retrieval, the
150-record evaluation harness and operational surfaces are implemented. Phase 4 ran
both selected providers from one commit, adopted a measured task router, and retained
the failures and limitations in the results and incident log.

| Phase | Scope | Status |
|---|---|---|
| 1 | Contracts, provider abstraction, CRM client, audit log, redaction, API skeleton, migrations | **Done** |
| 2 | Parsers, synthetic corpus, extraction, confidence scoring, CRM write path, review queue | **Done** |
| 3 | Corpus ingestion, chunking, embeddings, retrieval, cited synthesis, abstention | **Done** |
| 4 | Golden set, Haiku vs GPT Mini benchmark, measured router, metrics page, daily batch, incident log | **Done** |

The measured router uses `gpt-4o-mini` for bills, emails and QA, and
`claude-haiku-4-5` for site assessments. The numbers and their uncertainty are in
[`docs/RESULTS.md`](docs/RESULTS.md). Confidence did not calibrate monotonically, so
the 0.85 auto-write threshold remains an unpromoted placeholder, not a production
safety claim.

## Run it locally

```bash
git clone https://github.com/ozzy2438/SolarOps-Copilot.git
cd SolarOps-Copilot
cp .env.example .env          # works as-is; add API keys to make real model calls
docker compose up -d --build
curl -s localhost:8000/health/live     # {"status":"ok"}
```

`localhost:8000/docs` is the full API surface. `localhost:8080` is EspoCRM.
The rendered operational view is at `localhost:8000/metrics/page`.

`make down` stops the stack and keeps its data. Deleting VoltDesk's volumes is a
separate, confirmed command (`make destroy`).

### Rebuilding the golden set

The 110 synthetic extraction inputs used by the golden records are reproducible
Tier B artefacts and are intentionally ignored under `data/generated/`. Materialise
them before rebuilding the tracked golden JSON records:

```bash
make golden-set
```

This runs `scripts/materialise_generated.py` before `scripts/build_golden_set.py`.
The `test` and `verify` targets materialise the inputs automatically as well.

### Evaluation and daily regression check

Configure only the models you intend to call. Workspace-scoped Anthropic keys may set
`VOLTDESK_ANTHROPIC_WORKSPACE_ID`; ordinary keys leave it unset and no workspace
header is sent.

```bash
python -m voltdesk.evaluation.runner --model claude-haiku-4-5 --pilot-per-task 2
python -m voltdesk.evaluation.runner --benchmark
python -m voltdesk.batch --once
python -m voltdesk.batch --schedule   # enqueue the first RQ run for 24 hours later
```

The Compose worker runs with RQ's scheduler enabled. Invoke `--schedule` once per
deployment; each scheduled job enqueues its successor after it runs. The reduced
daily set is two records per task and opens an `app.incidents` row when exact match or
field recall drops by more than five percentage points from the latest comparable
run.

### Ports

The stack publishes exactly two ports on your machine:

| Service | Host port | Why it is published |
|---|---|---|
| `api` | 8000 | You call it |
| `espocrm` | 8080 | You browse it |

**PostgreSQL and Redis are not published at all.** `api` and `worker` reach them over
the Compose network at `postgres:5432` and `redis:6379`, so a host port would buy
nothing except a chance to collide with something else you run. Any fixed number here
would be a guess about your machine, and a wrong guess breaks `docker compose up`.

If 8000 or 8080 are taken, move VoltDesk rather than the thing that already holds the
port — set `VOLTDESK_API_HOST_PORT` / `VOLTDESK_ESPOCRM_HOST_PORT` in `.env`. To see
what holds a port first (read-only, changes nothing):

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
docker ps --format '{{.Names}}\t{{.Ports}}' | grep 8000
```

#### Reaching the database from the host

Most of the time you do not need to:

```bash
docker compose exec postgres psql -U voltdesk -d voltdesk
docker compose exec redis redis-cli
```

When you do want a host port — a GUI client, a local test run against the stack —
there is an opt-in overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.hostports.yml up -d
docker compose port postgres 5432        # the free port Docker picked
```

It leaves the host ports unset by default, so Docker assigns free ephemeral ones and
nothing can collide. Pin them with `VOLTDESK_POSTGRES_HOST_PORT` only after checking
the port is free, and point `VOLTDESK_DATABASE_URL` at the same number.

`VOLTDESK_DATABASE_URL` is commented out in `.env.example` deliberately: a default
pointing at `localhost:5432` would connect to whatever PostgreSQL you already run, and
applying VoltDesk's migrations there would create its schemas inside somebody else's
database.

## Architecture in one paragraph

FastAPI takes documents and questions. Documents are hashed, stored and enqueued to
Redis/RQ — the HTTP request never waits for a model. A worker parses (no model calls),
extracts (model call, through `LLMClient`), validates against a Pydantic contract,
repairs once on failure, calibrates per-field confidence, then writes the confident
fields to EspoCRM by idempotent upsert and queues the rest for a human. Questions go
through hybrid retrieval over pgvector, and either produce an answer whose every
citation was verified verbatim against its source chunk, or an explicit abstention.
Everything that crosses the trust boundary is redacted first, and every model call
writes an audit row whether it succeeded or not.

Full detail, including the failure-mode table: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## What makes this more than a demo

- **Confidence is structural, not decorative.** Every extracted value carries its
  confidence and the quote it came from (`ExtractedField[T]`), which is what makes
  "may this be written without a human?" an answerable question (ADR-0002).
- **Abstention is enforced by the contract.** `RetrievalAnswer` will not serialise an
  answer without a citation, or an abstention without a reason. An uncitable answer
  *is* an abstention, by construction (ADR-0012).
- **Every model call is audited, including the failures.** The audit write is in a
  `finally` block. Routing rationale, prompt version hash, tokens, cost at call time,
  latency, outcome, and whether redaction was applied.
- **Unverified facts are marked, never invented.** OpenAI pricing and live EspoCRM
  request shapes were verified in later phases; unresolved licences and NMI rules
  remain explicitly marked `TODO(verify)`. The cost path still refuses to publish
  from any model entry whose price is unverified.
- **Synthetic data with real physics.** Names and addresses are fabricated; tariff
  structures and interval data are real, because a synthetic bill with invented rates
  teaches a parser nothing (ADR-0013).

## Documentation

| Document | What it answers |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Components, both request flows, every failure mode, the trust boundary |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | 19 ADRs — why each non-obvious choice was made, and its consequences |
| [`docs/SCOPE.md`](docs/SCOPE.md) | What is in, what is permanently out, and why |
| [`docs/GUARDRAILS.md`](docs/GUARDRAILS.md) | Redaction policy, injection threat model, confidence bands, retry and breaker |
| [`docs/EVALUATION.md`](docs/EVALUATION.md) | The 150-record golden set and every metric definition |
| [`docs/RESULTS.md`](docs/RESULTS.md) | Same-commit benchmark results, uncertainty, router table and limitations |
| [`docs/INCIDENTS.md`](docs/INCIDENTS.md) | Real failures, blast radius, causes, remediation and related call IDs |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | Tier A real / Tier B synthetic, and the licence rule |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Orientation for the next phase: invariants, verification, open TODOs |
| [`voltdesk/contracts/README.md`](voltdesk/contracts/README.md) | The add-fields-never-rename rule and why it is load-bearing |
| [`crm/espocrm_entities.md`](crm/espocrm_entities.md) | The custom entities and field mapping |

## Stack

Python 3.11 · Pydantic v2 · FastAPI · PostgreSQL + pgvector · Redis + RQ ·
EspoCRM (REST only, never its database) · Anthropic and OpenAI official SDKs, called
directly. No agent framework, no orchestration library — both capabilities are
single-shot, and neither needs a model to decide what to do next (`docs/SCOPE.md`).
