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

**Blast radius:** Pilot only. Seven calls per provider were attempted; one QA record
per model abstained before a provider call. All fourteen rejected calls reported zero
input tokens, zero output tokens and USD 0.00 cost. The full 150-record runs were not
started, and the pre-existing `claude-opus-5` audit row was not part of this work.

**Root cause:** The Anthropic credential is workspace-scoped but no workspace ID is
configured. Independently, the OpenAI adapter had never been exercised live with
strict structured outputs and did not convert optional Pydantic properties into
OpenAI's all-properties-required schema form.

**Remediation:** The OpenAI adapter now creates a provider-specific strict schema,
including nested definitions and reference siblings, without changing the committed
provider-neutral schemas; regression tests pin the conversion. The rerun passed an
8-record pilot and then completed all 150 records from commit `5ca8b4c`. The full run
reported USD 0.194148 evaluation cost. A PostgreSQL backend restart after record 75
was recovered through the existing checkpoint/resume path; the uncheckpointed
`email-0026` request was repeated, adding USD 0.001230 to the audit ledger but not to
the benchmark result. Anthropic remains blocked until the matching workspace ID is
supplied or the key is replaced with one that does not require it.

**Related `call_id`s:** Anthropic representative
`00b1d97c-eb97-4562-85ac-c04d69d60244`; OpenAI representative
`9a9a4db2-a32a-4fb7-acf9-34755744bf0a`. The complete sets remain in
`app.model_calls` under model IDs `claude-haiku-4-5` and `gpt-4o-mini`.
