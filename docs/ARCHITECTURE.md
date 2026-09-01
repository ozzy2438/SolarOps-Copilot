# Architecture

## What this is

VoltDesk is an LLM service layer beside the CRM of a commercial solar and battery
installer. Two capabilities, nothing else:

1. **Document intake.** Electricity bills, site assessment notes and email threads
   become schema-validated structured records, written idempotently into EspoCRM.
2. **Knowledge Q&A.** Staff questions about the company's own technical and
   compliance material, answered with citations, or explicitly refused.

## Component map

```
                       ┌────────────────────────────────────────────┐
   HTTP ──────────────▶│  FastAPI  (voltdesk/api)                   │
                       │  /documents  /qa  /review  /admin          │
                       │  /health     /metrics                      │
                       └───────┬────────────────────────┬───────────┘
                               │ enqueue                │ read
                               ▼                        ▼
                    ┌──────────────────┐      ┌──────────────────────┐
                    │  Redis + RQ      │      │  PostgreSQL          │
                    │  (jobs only)     │      │  schema app  (data)  │
                    └────────┬─────────┘      │  schema vec  (pgvector)
                             │                └──────────┬───────────┘
                             ▼                           │
                  ┌────────────────────┐                 │
                  │  Worker            │                 │
                  │  parse → extract   │─────────────────┘
                  │  → validate → write│
                  └─────────┬──────────┘
                            │
              ┌─────────────┴──────────────┐
              ▼                            ▼
   ┌────────────────────┐        ┌────────────────────┐
   │  LLMClient         │        │  EspoCrmClient     │
   │  redact → route    │        │  REST, idempotent  │
   │  → call → audit    │        │  upsert            │
   └─────────┬──────────┘        └─────────┬──────────┘
             │                             │
   ═══════ TRUST BOUNDARY ═══════          │
             │                             │
             ▼                             ▼
   ┌────────────────────┐        ┌────────────────────┐
   │ Anthropic / OpenAI │        │  EspoCRM (Docker)  │
   └────────────────────┘        └────────────────────┘
```

VoltDesk never touches the EspoCRM database. Only the REST API.

## Request flow: document intake

1. `POST /documents` — bytes are hashed, stored in `app.documents`, an RQ job is
   enqueued. The response is 202 with a document id. **The request does not wait for
   a model.** A bill with a bad OCR path can take thirty seconds; an HTTP request
   should not.
2. Worker parses (`voltdesk/parsers`) → `ParsedDocument`. No model call yet.
3. Worker extracts (`voltdesk/extraction`) via `LLMClient`. The payload is redacted
   before it crosses the boundary. The response is validated against the contract.
4. On `ValidationError`: one repair attempt with the error fed back. Still invalid →
   the document is marked failed and queued for review. Never a silent partial write.
5. Confidence calibration (`voltdesk/extraction/confidence.py`) assigns each field to
   a band: auto-write, review, or drop (`docs/GUARDRAILS.md`).
6. Fields above the threshold are written to EspoCRM via idempotent upsert on the
   external key. Fields below go to `app.review_queue`. If a *blocking* field (the
   NMI on a bill) is uncertain, nothing is written at all.
7. Every model call in steps 3–4 wrote a row to `app.model_calls`, whether it
   succeeded or failed.

## Request flow: knowledge Q&A

1. `POST /qa/ask` with a `RetrievalQuery`.
2. Hybrid retrieval over `vec.chunks` — vector similarity plus lexical search.
   Lexical matters here: staff ask about clause numbers and model numbers, which
   embeddings blur.
3. `support_score` is computed from the retrieved evidence.
4. Below `VOLTDESK_ABSTENTION_THRESHOLD` → abstain with a reason. No model call is
   made. Abstaining cheaply is a feature.
5. Above it → synthesis with citations, then **verification**: every citation quote
   must appear verbatim in the chunk it names. A failed verification turns the answer
   into an abstention rather than a warning.
6. `RetrievalAnswer` is returned. Its validator enforces that an answer has at least
   one citation and an abstention has none.

## Failure modes and how each is handled

| Failure | Handling |
|---|---|
| Provider timeout or 5xx | Retry with exponential backoff, bounded by `llm_max_retries`. Audited with `outcome=timeout` or `provider_error`. |
| Provider repeatedly failing | Circuit breaker opens after `circuit_breaker_failure_threshold` consecutive failures; calls fail fast with `outcome=circuit_open` until the reset window elapses. |
| Provider entirely unavailable | Router's `fallback()` crosses to the other provider — but returns `None` rather than degrading to an unmeasured model when the other is also unusable. The request fails and says so. |
| Model returns invalid JSON | Caught as `ValidationError`, one repair attempt, then review queue. Audited as `schema_invalid`. |
| Model refuses (safety classifier) | HTTP 200 with `stop_reason="refusal"`. Detected explicitly, audited as `refusal`, never treated as an empty answer. |
| Extraction is low-confidence | Review queue. Nothing below the threshold reaches the CRM. |
| CRM unreachable | Job retries; the extraction is already persisted, so nothing is lost. Typed `CrmUnavailableError` distinguishes it from a bad payload. `/health/ready` reports it as reachable=false with the connection error. |
| CRM configured but rejecting the key | Reported as `reachable: true, authenticated: false` with the status code. A 401 means EspoCRM is *up* — reporting that as "down" sends the operator to look at the wrong thing. |
| CRM not configured at all | Reported as `configured: false` and listed under `unconfigured`. Not a readiness failure: no EspoCRM API key exists until someone creates an API user by hand, and reporting a correct fresh install as 503 trains people to ignore the endpoint. Phase 2 tightens this once the write path exists. |
| CRM rejects the payload | `CrmValidationError` — not retried, because retrying a 400 hides the real problem (usually a custom field missing from the instance). |
| Duplicate external key in the CRM | Refused rather than resolved arbitrarily. Two records sharing an external key means the uniqueness constraint is missing. |
| Database down | The API's `/health/ready` reports which dependency failed. Audit writes fail soft — the structured log line survives — because losing an audit row is bad but failing a customer document because the audit table is unreachable is worse. |
| Retrieval finds nothing relevant | Abstention with `no_relevant_evidence`. Not an error. |
| Citation cannot be verified | The answer becomes an abstention. |

## The trust boundary

The boundary is `LLMClient.complete()`. Above it, data is whatever the customer sent.
Below it, data has left the building.

Everything crossing it passes through a `Redactor` first, and the audit record carries
`redaction_applied` plus per-entity counts. A row with `redaction_applied=false` on a
call that carried customer data is an incident, not a metric.

What is redacted, what is not, and the known gaps are in `docs/GUARDRAILS.md`.

Two further boundary facts, stated rather than left implicit:

- **The service has no authentication.** RBAC is permanently out of scope. VoltDesk
  must therefore be deployed inside the company's own network boundary, never exposed
  to the internet. This constrains deployment; it is not an oversight.
- **The corpus is Tier A only.** Real, publicly sourced material. Customer documents
  are never ingested into the retrieval corpus, so a Q&A answer can never leak one
  customer's data to another user.

## Why these boundaries

The seams are placed where the phases divide, so that a phase can be verified in
isolation:

- **Parsers never call models; extractors never open files.** Phase 4 can measure
  extraction quality without a PDF library in the loop.
- **`LLMClient` is the only supported way to call a provider.** Redaction and audit
  are structural, not conventions a later phase can forget. That is why the audit
  write is in a `finally` block.
- **Cost is computed at call time, never at read time.** A price change must not
  silently rewrite history.
- **`app` and `vec` are separate schemas.** A corpus re-embed truncates `vec` without
  touching anything operational.
