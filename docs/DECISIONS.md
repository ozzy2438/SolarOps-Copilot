# Architecture Decision Records

Numbered, append-only. Later phases add ADRs; they do not edit existing ones. If a
decision is reversed, write a new ADR that supersedes the old one and say so in both.

Format: context, decision, consequences. The consequences section matters most —
it is what tells a later phase whether the decision is still holding.

---

## ADR-0001: The repository is named SolarOps-Copilot; the system is named VoltDesk

**Context.** The Phase 1 brief specifies a system named VoltDesk. The GitHub
repository it is being built in is named `SolarOps-Copilot`.

**Decision.** Keep both. The Python package, the service, the Docker services and
all documentation say VoltDesk. The repository keeps its existing name and URL.

**Consequences.** A reader arriving from the repository URL sees a different name in
the README's first line. `README.md` states the relationship in its opening
paragraph so this is never a surprise. Renaming the repository later breaks any
existing link and is not worth doing for cosmetics.

---

## ADR-0002: Every extracted value is wrapped in `ExtractedField`

**Context.** The system must decide, per field, whether a value may be written to
the CRM without a human. A bare extracted value carries no basis for that decision.

**Decision.** Every business field on every extraction contract is
`ExtractedField[T]`, carrying `value`, `confidence`, `source_quote`, `source_page`.

**Consequences.** Contracts are more verbose and JSON payloads are larger — roughly
three to four times the size of a flat record. In exchange the confidence-band policy,
the review queue and the coverage-accuracy curve are all expressible. `value=None,
confidence=0.0` means *absent from the document*, distinct from a low-confidence
guess; every phase must preserve that distinction.

---

## ADR-0003: `extra="forbid"` on every contract

**Context.** Models invent plausible-looking fields. Pydantic's default silently
drops unknown keys.

**Decision.** `StrictModel` sets `extra="forbid"`, so an unknown key raises
`ValidationError`.

**Consequences.** Extraction failures are noisier — a model that adds one invented
field fails the whole extraction rather than producing a mostly-correct record. That
is the intended trade: the schema repair loop and the `schema_invalid` audit outcome
both depend on the failure being raised. Phase 2 must budget for repair attempts.

---

## ADR-0004: Plain SQL migrations, not Alembic

**Context.** The schema is eight tables and changes rarely. The local stack is Docker
Compose, whose PostgreSQL image applies `.sql` files from a mounted directory on first
start.

**Decision.** Numbered plain-SQL files in `migrations/`, applied in filename order.
Every statement idempotent.

**Consequences.** No autogeneration, no downgrade path, no migration history table.
Applying migrations to an existing database is a shell loop, documented in
`migrations/README.md`. Committed migrations are never edited — a later phase that
edits `0001` leaves every existing database in a state no migration describes. If the
schema ever starts changing weekly, revisit this with a superseding ADR.

---

## ADR-0005: One database, two schemas (`app` and `vec`)

**Context.** Application data and vector storage have different lifecycles. A corpus
re-embed replaces every vector; nothing operational should be at risk.

**Decision.** One PostgreSQL database. `app` for documents, extractions, review queue,
audit log, evaluation runs, incidents. `vec` for corpus documents, chunks, embeddings.

**Consequences.** `TRUNCATE vec.embeddings CASCADE` is a safe operation. One database
means one backup, one connection pool, one thing to restart — which matters on a
single small VM. A second vector database is permanently out of scope.

---

## ADR-0006: `LLMClient` is the only supported way to call a provider

**Context.** Redaction and audit logging must be structural. If they are conventions,
some later phase will forget one.

**Decision.** Provider adapters are not part of the public surface. Everything calls
`LLMClient.complete()`, which redacts, retries, applies the circuit breaker, and
writes an audit record in a `finally` block.

**Consequences.** The adapters cannot expose provider-specific features that do not
fit `CompletionRequest`. That is deliberate: anything a provider offers that cannot
be measured in the same units on both sides does not get used, because the routing
and benchmark phases depend on comparability. Adding a feature means widening the
contract for both providers, or not at all.

---

## ADR-0007: Cost is computed at call time and stored

**Context.** Provider prices change. Reports must remain reproducible.

**Decision.** `compute_cost_usd` runs at call time; the result is stored on the audit
row. Nothing recomputes cost at read time.

**Consequences.** A price change does not rewrite history — but it also does not
correct a past mistake in the price table. If a price is found to have been wrong,
the fix is a new ADR and a documented correction, not an `UPDATE`.

---

## ADR-0008: Unverified prices refuse to be published

**Context.** Phase 1 verified Anthropic model identities and pricing. It did not have
an OpenAI credential and did not verify OpenAI's. Inventing a plausible price is the
single worst failure mode available here, because Phase 4 would build a published
cost comparison on it.

**Decision.** `ModelPrice.verified` is `False` for every OpenAI entry, with zeroed
prices and a `TODO(verify)` note. `assert_verified(model_id)` raises
`UnverifiedPriceError`. Phase 4 must call it before publishing any cost figure.

**Consequences.** Phase 4 cannot publish a Claude-vs-GPT cost comparison until it
verifies OpenAI's pricing and flips the flag. A test pins this
(`tests/test_pricing.py`). The system still *runs* against OpenAI — only the
published cost number is gated.

---

## ADR-0009: The NMI is not personal information and is deliberately preserved

**Context.** The National Metering Identifier is the join key between a bill, a site,
a grid connection and a network tariff. Redacting it would break every downstream
join and make extraction useless.

**Decision.** The NMI is classified as a site identifier, not personal information,
and is intentionally not on the redaction list.

**Consequences.** Two things follow. First, an NMI reaching a provider is expected
behaviour, not an incident. Second — and this is a real open problem — the current
`RegexRedactor`'s `ACCOUNT_NUMBER` pattern matches long digit runs and therefore
*does* redact NMIs today. `tests/test_redaction.py` documents this rather than
pretending otherwise, and `docs/GUARDRAILS.md` carries the TODO. Phase 2 must fix
the pattern before extraction quality can be measured, because a redacted NMI makes
every bill extraction unmatched.

---

## ADR-0010: The Phase 1 router is deliberately naive

**Context.** Choosing a cheaper model per task before measuring that task is a guess.
A guess recorded in the audit log is indistinguishable from a measurement six months
later.

**Decision.** `StaticRouter` always returns the default model, and its `rationale`
field says in words that it is a default and not a measured choice.

**Consequences.** Phase 1 costs more per document than it needs to. Phase 4 replaces
this with a task table derived from the benchmark and records the change as an ADR.
Until then, every audit row is honest about why its model was chosen.

---

## ADR-0011: The circuit breaker is process-local

**Context.** The API and the worker are separate processes. A shared breaker would
need Redis state and a lock.

**Decision.** Breaker state lives in `ProviderRegistry`, per process.

**Consequences.** Each process discovers a provider outage independently, so the
first N calls in each process fail before its breaker opens. With two processes and
a threshold of five, that is at most ten wasted calls per outage — acceptable, and
much cheaper than distributed breaker state. Revisit if the deployment ever runs
many workers.

---

## ADR-0012: Abstention is a first-class outcome, enforced by the contract

**Context.** The staff asking these questions are making compliance decisions. A
confident wrong answer about an export limit is worse than no answer.

**Decision.** `RetrievalAnswer` has a model validator: an abstained answer carries a
reason and no text; an answered query carries at least one citation. An uncitable
answer is an abstention, by construction.

**Consequences.** Phase 3 cannot return an answer it cannot cite, even as a
"best effort with a warning" — the contract will not serialise. Abstention rate
becomes a headline metric rather than a hidden failure, and Phase 4 measures
abstention precision and recall explicitly.

---

## ADR-0013: Synthetic documents, real physics and real prices

**Context.** The repository must contain no real personal information. It must also
train and test parsers against realistic material.

**Decision.** Tier B synthetic documents fabricate names, addresses, account numbers
and contacts, but are built on **real tariff structures and real interval data**.
Deliberate defects (skew, no text layer, split tables, mixed date formats, missing
fields, two retailer layouts) are injected on purpose.

**Consequences.** The generator needs real source data that must be licence-checked
before it is committed — `docs/DATA_SOURCES.md` carries those TODOs, and they are
open. A generated corpus is reproducible from a seed, and ground truth comes free
(`ground_truth_source='generator_seed'`), which is most of the golden set's value.

---

## ADR-0014: Inbound document bytes live in Postgres, not on a host volume

**Context.** `app.documents` in `0001` stored `sha256` and `byte_size` but not the
file. Phase 2's API and RQ worker must both read the original bytes after
`POST /documents` returns 202. They share Postgres already. A host-mounted volume
would be a second store to keep in sync, and Compose deliberately does not publish
Postgres on the host.

**Decision.** Add `app.documents.content BYTEA` in `migrations/0005_document_bytes.sql`.
The same row is the document record and the payload. Duplicate `sha256` still
collapses to one row (`documents_sha256_key`). Phase 3 vector-dimension changes
start at `0006`; `0003`'s 1536 placeholder is untouched.

**Consequences.** Large PDFs live in the operational database. That is acceptable
at the volume of bills and site notes this service is for. Object storage would
need a new dependency and a consistency story the worker does not have. Existing
databases created from `0001`–`0004` pick this up by running the migration loop;
Compose initdb on a fresh volume applies `0005` automatically.

---

## ADR-0015: Pin local 384-dimensional MiniLM embeddings

**Context.** Knowledge retrieval needs a reproducible embedding model whose licence,
revision and vector dimension are explicit. Provider embeddings would add credentials,
cost and an external data path to an otherwise local corpus workflow. The committed
`0003` migration deliberately left a 1536-dimensional placeholder for Phase 3 to
replace through a new migration.

**Decision.** Use `sentence-transformers/all-MiniLM-L6-v2` at immutable revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, under Apache-2.0. Store its full
repository-and-revision identity with every normalized 384-dimensional vector.
Load it locally and lazily; do not send corpus text to an embedding provider.
`0006_embedding_dimension.sql` changes an empty placeholder column to `vector(384)`
and refuses to reinterpret a non-empty 1536-dimensional corpus.

**Consequences.** The model download is about 91 MB and inputs beyond the model's
256-wordpiece limit are truncated, so structural chunks remain intentionally small.
Changing the model or revision requires another ADR, a dimension-compatible migration
when necessary, and explicit full-corpus re-embedding. A process cannot silently mix
models or dimensions in one corpus.

---

## ADR-0016: Run pinned MiniLM as a CPU-only ONNX artifact

**Context.** ADR-0015 selected the MiniLM network and 384-dimensional contract. Its
first `sentence-transformers` implementation pulled GPU/CUDA runtime packages into the
Linux service image even though VoltDesk runs embedding inference on CPU. That made the
otherwise small service image unnecessarily large and made Compose acceptance costly.

**Decision.** Preserve the same `all-MiniLM-L6-v2` network, Apache-2.0 licence, input
limit and 384-dimensional normalized output, but execute Qdrant's official ONNX port
with FastEmbed's CPU execution provider. Pin the ONNX artifact repository revision to
`Qdrant/all-MiniLM-L6-v2-onnx@5f1b8cd78bc4fb444dd171e59b18f3a3af89a079`
and store that exact runtime artifact identity with every vector. This supersedes only
ADR-0015's stored repository identity and runtime implementation; the selected model
and migration dimension do not change.

**Consequences.** The service no longer installs PyTorch or CUDA. The model remains a
lazy local download and no corpus text is sent to an inference provider. Any future
ONNX artifact change still requires an ADR and full-corpus re-embedding, even when its
dimension remains 384.

---

## ADR-0017: Anthropic workspace routing is explicit and optional

**Context.** Anthropic accepts ordinary API keys without a workspace header, while
some workspace-scoped keys reject requests unless `anthropic-workspace-id` identifies
their workspace. Sending a made-up, empty or unrelated identifier would break keys
that do not use this mechanism and could route a request to the wrong workspace.

**Decision.** Add the optional `VOLTDESK_ANTHROPIC_WORKSPACE_ID` setting. When its
trimmed value is non-empty, `AnthropicProvider` supplies it to the official SDK as the
`anthropic-workspace-id` default header. When it is absent or empty, the adapter does
not configure that header at all. The value remains local configuration and is never
committed.

**Consequences.** Workspace-scoped credentials require one additional deployment
setting; ordinary credentials behave exactly as before. A missing workspace ID for a
key that requires one fails visibly at Anthropic's boundary rather than being guessed.
Changing workspaces is a configuration change, not an application-code change.

---

## ADR-0018: Route by same-commit task measurements

**Context.** ADR-0010 deliberately used a static default because no task-level
comparison existed. Phase 4 completed `claude-haiku-4-5` run
`eval-8325bd1c-879b-49a0-a858-b3d405377b8f` and `gpt-4o-mini` run
`eval-8d41a233-c32d-4318-892d-02c8c6f1ff00`, both over 150 records at commit
`f1f10ad03df810eaa2127167369044b5f943b59b`.

**Decision.** Replace the static policy with `TaskRouter`. Use GPT Mini for bills,
emails, QA and schema repair; use Haiku for site assessment. Exact match was tied on
bills and emails, the QA intervals overlapped while GPT cost less, and Haiku's site
interval did not overlap GPT's. Every routing rationale names the measurement runs.
Fallback can use only the other measured model and only when its credential is usable.

**Consequences.** Routing is evidence-based but bound to this synthetic-heavy golden
set and point-in-time provider behaviour. A new golden-set version or model version
requires a new benchmark and superseding ADR. `StaticRouter(registry)` remains a
compatibility constructor so existing call sites adopt the measured router without
editing Phase 2/3 modules that Phase 4 is forbidden to change.

---

## ADR-0019: Do not promote an uncalibrated confidence threshold

**Context.** The combined routed field curve reached 96.06% accuracy at confidence
0.95, then fell to 95.05% at 1.00. A confidence score whose higher bucket is less
accurate is not calibrated under the binding evaluation rule.

**Decision.** Do not derive a replacement for
`VOLTDESK_AUTO_WRITE_CONFIDENCE_THRESHOLD`. Keep 0.85 as an explicitly unpromoted
placeholder and require human review for any operational deployment until confidence
is recalibrated on representative, human-labelled extraction data.

**Consequences.** The current 0.85 setting must not be described as a measured safety
boundary. It preserves compatibility for development and evaluation, but unattended
CRM auto-write is not justified by Phase 4. A future threshold change must carry a
monotonic coverage-accuracy curve and a superseding ADR.
