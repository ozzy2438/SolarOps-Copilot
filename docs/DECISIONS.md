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

## ADR-0014: NMIs are identified by label, not by a checksum

**Context.** ADR-0009 says the NMI is not redacted. The `ACCOUNT_NUMBER` pattern
matched 8–12 digit runs and therefore swallowed every numeric NMI. The AEMO NMI
Procedure checksum is still `TODO(verify)`; inventing a pattern would be worse than
leaving the gap, because Phase 4 would treat a guessed checksum as a real filter.

**Decision.** Treat a 10–11 character token as an NMI when the document labels it
`NMI` or `National Metering Identifier`. Protect that value for the rest of the
string, including later unlabelled repeats. Do not invent a checksum.

**Consequences.** A labelled NMI survives redaction and remains the join key.
An unlabelled 10–11 digit run is still redacted as an account number. Bills in this
corpus (and real Australian bills) print the NMI with that label; that is the path
extraction is measured on. If a later phase verifies the checksum, a superseding
ADR can widen protection to unlabelled tokens that pass it.
