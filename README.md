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

**Phase 1 of 4 — foundation complete.** The contracts, the trust boundary, the CRM
client, the audit log and the API skeleton are implemented and tested. The two
capabilities themselves are not yet built; every unimplemented component raises
`NotImplementedError` naming the phase that owns it, and every unimplemented route
returns `501` naming the same.

| Phase | Scope | Status |
|---|---|---|
| 1 | Contracts, provider abstraction, CRM client, audit log, redaction, API skeleton, migrations | **Done** |
| 2 | Parsers, synthetic corpus, extraction, confidence scoring, CRM write path, review queue | Not started |
| 3 | Corpus ingestion, chunking, embeddings, retrieval, cited synthesis, abstention | Not started |
| 4 | Golden set, Claude vs GPT benchmark, measured router, metrics page, daily batch, incident log | Not started |

There are no benchmark numbers yet. Phase 4 produces them, and
`voltdesk/llm/pricing.py` will refuse to publish a cost figure derived from an
unverified price until then (ADR-0008).

## Run it locally

```bash
git clone https://github.com/ozzy2438/SolarOps-Copilot.git
cd SolarOps-Copilot
cp .env.example .env          # works as-is; add API keys to make real model calls
docker compose up -d --build
curl -s localhost:8000/health/live     # {"status":"ok"}
```

`localhost:8000/docs` is the full API surface. `localhost:8080` is EspoCRM.

`make down` stops the stack and keeps its data. Deleting VoltDesk's volumes is a
separate, confirmed command (`make destroy`).

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
- **Unverified facts are marked, never invented.** Phase 1 did not have an OpenAI
  credential or a live EspoCRM instance, so those prices and request shapes are
  `TODO(verify)` and the cost path refuses to publish from them. `grep -rn "TODO(verify)"`
  shows everything still open.
- **Synthetic data with real physics.** Names and addresses are fabricated; tariff
  structures and interval data are real, because a synthetic bill with invented rates
  teaches a parser nothing (ADR-0013).

## Documentation

| Document | What it answers |
|---|---|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Components, both request flows, every failure mode, the trust boundary |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | 13 ADRs — why each non-obvious choice was made, and its consequences |
| [`docs/SCOPE.md`](docs/SCOPE.md) | What is in, what is permanently out, and why |
| [`docs/GUARDRAILS.md`](docs/GUARDRAILS.md) | Redaction policy, injection threat model, confidence bands, retry and breaker |
| [`docs/EVALUATION.md`](docs/EVALUATION.md) | The 150-record golden set and every metric definition |
| [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) | Tier A real / Tier B synthetic, and the licence rule |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | Orientation for the next phase: invariants, verification, open TODOs |
| [`voltdesk/contracts/README.md`](voltdesk/contracts/README.md) | The add-fields-never-rename rule and why it is load-bearing |
| [`crm/espocrm_entities.md`](crm/espocrm_entities.md) | The custom entities and field mapping |

## Stack

Python 3.11 · Pydantic v2 · FastAPI · PostgreSQL + pgvector · Redis + RQ ·
EspoCRM (REST only, never its database) · Anthropic and OpenAI official SDKs, called
directly. No agent framework, no orchestration library — both capabilities are
single-shot, and neither needs a model to decide what to do next (`docs/SCOPE.md`).
