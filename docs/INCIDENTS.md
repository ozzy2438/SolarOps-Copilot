# Incident log

## 2026-09-02 — Clean-clone golden-set inputs were missing

**What happened:** The Phase 4 report said `136 passed`, but a clean clone reported
`134/2 failed`. In the words of the handoff: “Faz 4 raporu 136 passed dedi, temiz klonda 134/2 failed; kök neden gitignore edilmiş üretilmiş veriye bağımlılık”. The failing checks were the golden-set checks that load extraction records.

**Blast radius:** A fresh checkout could not load the 110 extraction records whose
`input_path` points into `data/generated/`. Existing worktrees with previously
materialised files were unaffected. No model call or production customer data was
involved.

**Root cause:** `data/generated/` is correctly excluded from git because the files
are deterministic synthetic Tier B artefacts, but the verification path assumed the
ignored files already existed. `build_golden_set.py` created the JSON records without
an explicit checkout-time materialisation step.

**Remediation:** Added `scripts/materialise_generated.py`, pinned to generator seed 7
and the 50/30/30 extraction split. `make golden-set` now materialises the documents
before rebuilding records, and `make test`/`make verify` make the same step an
explicit prerequisite. README instructions document the order.

**Related `call_id`s:** None — the failure occurred before any provider or model call.

## 2026-09-02 — Live benchmark pilot was rejected at both provider boundaries

**What happened:** The requested 8-record-per-model pilot reached both provider APIs,
but no completion was accepted. Anthropic returned HTTP 400 because the configured
key requires an `anthropic-workspace-id`. OpenAI returned HTTP 400 because VoltDesk
sent the ordinary Pydantic schema directly into strict structured-output mode, where
every property must appear in `required`. Both evaluation runs checkpointed eight
failed records and remained unfinished because field precision was undefined.

**Blast radius:** The initial pilot only. Seven calls per provider were attempted; one
QA record per model abstained before a provider call. All fourteen rejected calls
reported zero input tokens, zero output tokens and USD 0.00 cost. No
`claude-opus-5` call was made.

**Root cause:** The Anthropic credential is workspace-scoped but no workspace ID is
configured. Independently, the OpenAI adapter had never been exercised live with
strict structured outputs and did not convert optional Pydantic properties into
OpenAI's all-properties-required schema form.

**Remediation:** The OpenAI adapter now creates a provider-specific strict schema,
including nested definitions and reference siblings, without changing the committed
provider-neutral schemas; regression tests pin the conversion. The optional
`VOLTDESK_ANTHROPIC_WORKSPACE_ID` setting now sends
`anthropic-workspace-id` only when configured (ADR-0017). Anthropic structured-output
normalisation, model-capability gating for adaptive thinking and a grammar-size
fallback were also pinned by regression tests. The Haiku rerun passed an eight-record
pilot, then both providers completed 150 records from the same commit `f1f10ad`; the
reproducible run IDs and results are in `docs/RESULTS.md`.

**Related `call_id`s:** Anthropic representative
`00b1d97c-eb97-4562-85ac-c04d69d60244`; OpenAI representative
`9a9a4db2-a32a-4fb7-acf9-34755744bf0a`. The complete sets remain in
`app.model_calls` under model IDs `claude-haiku-4-5` and `gpt-4o-mini`.

## 2026-09-02 — PostgreSQL interruption left a completed provider call uncheckpointed

**What happened:** During the Haiku pilot the local Docker/PostgreSQL service stopped
responding after a site-assessment provider call had succeeded and been written to the
audit path but before the evaluation checkpoint committed. After a controlled Docker
Desktop restart and run resume, that record was executed again. The full OpenAI run
also encountered a PostgreSQL backend restart and resumed from its last checkpoint.

**Blast radius:** Local Phase 4 benchmark infrastructure only. No source or customer
data was lost. The Haiku pilot evaluation includes one site result once, while its
audit ledger correctly contains both paid provider calls. This adds about USD 0.006
to the pilot ledger. The full same-commit benchmark runs completed.

**Root cause:** The development Docker/PostgreSQL service suffered an I/O/backend
interruption. Per-record checkpointing prevents loss of committed progress but cannot
atomically join a third-party provider response to the subsequent PostgreSQL
checkpoint; an interruption in that gap produces at-least-once model execution.

**Remediation:** Docker Desktop was restarted without deleting volumes, PostgreSQL
health and restart count were checked, and the run resumed against an isolated Compose
project/volume. The 3-document, 12-chunk corpus was materialised in that isolated
database before QA was retried. The orphan call is retained rather than deleted or
folded into the evaluation cost. A production follow-up should add an idempotency key
or durable pre-call state if the provider supports it; Phase 4 does not change the
audit/checkpoint boundary.

**Related `call_id`s:** orphaned site call
`3010d148-5b55-4138-b2b2-a06521ac1710`; repeated site call
`4ce0d696-ca3d-42b0-900b-92e649dc66a9`; preceding site call
`9c095145-e1cb-4014-aa83-e5f15da3601d`.
