# Phase 2 — Document intake

## Objective

Make the first capability real. A bill, a site assessment or an email thread arrives
at `POST /documents`, and a validated, confidence-scored record lands in EspoCRM —
or in the review queue when the system is not sure enough to write it unattended.
You build the synthetic corpus this runs against, the parsers that read it, the
extraction prompts, the confidence calibration that makes the auto-write decision
meaningful, the CRM write path, and the human review queue. You do not touch
retrieval, evaluation or routing.

## Files you create or modify

Create:

- `voltdesk/synthetic/generator.py` (implement)
- `voltdesk/parsers/bill_parser.py`, `site_notes_parser.py`, `email_parser.py`
- `voltdesk/extraction/prompts.py`, `extractor.py`, `confidence.py` (implement)
- `voltdesk/crm/writer.py` (new — the write path)
- `voltdesk/review/queue.py` (implement)
- `voltdesk/jobs.py` (new — RQ job functions)
- `tests/test_parsers.py`, `test_extraction.py`, `test_confidence.py`,
  `test_review.py`, `test_crm_writer.py`
- `tests/fixtures/` — recorded LLM responses

Modify:

- `voltdesk/api/routes/documents.py`, `review.py` — replace the 501s
- `tests/test_phase2_stubs.py` — replace each stub test with a real one. **Do not
  delete it.** A disappearing test is indistinguishable from a forgotten one.
- `PROGRESS.md` — your report
- `docs/DECISIONS.md` — append ADRs; never edit existing ones

**Do not touch:**

`voltdesk/contracts/` (except to *add* an optional field, and only with an ADR) ·
`voltdesk/llm/` · `voltdesk/audit/` · `voltdesk/crm/client.py` ·
`voltdesk/routing/` · `voltdesk/retrieval/` · `voltdesk/ingestion/` ·
`voltdesk/evaluation/` · `migrations/0001`–`0004` (add `0005_*.sql` if you need
schema) · `docs/SCOPE.md` · `docs/ARCHITECTURE.md` · `schemas/` (regenerate, never
hand-edit).

## Contracts you consume and produce

**Consume:** `ParsedDocument`, `ParsedPage`, `GeneratorConfig`, `Settings`,
`CompletionRequest`/`CompletionResponse`, `RoutingDecision` (from `StaticRouter`).

**Produce:** `ExtractedBill`, `ExtractedSiteAssessment`, `ExtractedEmailThread`,
`EnergyProfilePayload`, `SiteAssessmentPayload`, `ReviewItem`, `FieldForReview`,
`GeneratedDocument`.

## Implementation steps, in order

**Step 0 — fix the redaction bug first.** `ACCOUNT_NUMBER` in
`voltdesk/redaction/regex_redactor.py` matches 8–12 digit runs, which includes NMIs.
ADR-0009 says the NMI must be preserved; the code contradicts it. A redacted NMI makes
every bill extraction unmatched and would dominate Phase 4's numbers. Fix the pattern,
update `tests/test_redaction.py` (the current test documents the bug — replace it with
one asserting the intended behaviour), and note it in your report. **Nothing else you
do this phase matters if you skip this.**

**Step 1 — synthetic generator.** Implement `SyntheticGenerator.generate()` per
`voltdesk/synthetic/spec.py`. Deterministic from `seed`. Real tariff structures and
real interval data (`docs/DATA_SOURCES.md`) with fabricated identities. Inject the
defects. Emit `GeneratedDocument` with `ground_truth` alongside every file — that
ground truth is most of Phase 4's golden set, and it is free only if you write it now.

**Step 2 — parsers.** Bytes → `ParsedDocument`. No model calls. Set `used_ocr`,
`skew_degrees` and `warnings` honestly. Preserve table structure: a bill's meaning
lives in its tariff table, and flattening it loses the association between a rate and
its label.

**Step 3 — prompts.** System prompt carries the instructions and the JSON Schema read
from `schemas/`, and is **stable across calls** so the prompt cache works. Document
text goes in the user message. Instruct the model to emit `value: null,
confidence: 0.0` for absent fields and **not to guess** — the review queue's behaviour
depends on "absent" and "unsure" being different things.

**Step 4 — extractor.** Call through `LLMClient`. Validate. On `ValidationError`, one
repair attempt with the error fed back; still invalid → mark failed and queue for
review. One attempt, not a loop (`docs/GUARDRAILS.md`).

**Step 5 — schema repair.** Implement `repair_prompt`. Audited as `schema_invalid`.

**Step 6 — confidence calibration.** The strongest signal is `verify_quote`: does the
cited span actually appear in the document? A value the model invented usually carries
an invented quote. Implement `calibrate`, `classify_for_write`, `min_confidence`.
Treat an extraction whose fields are uniformly 1.0 as suspicious, not excellent.

**Step 7 — CRM write path.** `voltdesk/crm/writer.py`: extraction → payload via
`voltdesk/crm/mapping.py` → `EspoCrmClient.upsert`. Auto-write only fields above the
threshold. **A bill whose NMI is uncertain is blocking — write nothing from that
document.**

**Step 8 — review queue.** Implement `ReviewQueue` against `app.review_queue`. Retain
`corrections`; Phase 4 mines them as ground truth.

**Step 9 — wire up the routes and the RQ job.** Replace the 501s in `documents.py`
and `review.py`. `POST /documents` returns 202 immediately and enqueues — it must not
wait for a model.

## Acceptance criteria

Each is a command and its expected output.

- [ ] `make verify` → clean; ruff, mypy, pytest, no schema drift
- [ ] `pytest tests/test_redaction.py -q` → passes, including a test asserting an NMI
      survives redaction
- [ ] `python -c "from voltdesk.synthetic import *; d=SyntheticGenerator(GeneratorConfig(seed=7)).generate(); print(len(d))"` → `150`
- [ ] Same seed twice produces byte-identical files:
      `python scripts/check_generator_determinism.py` → `deterministic: OK` (you write this)
- [ ] `pytest tests/test_parsers.py -q` → passes, covering a skewed scan, a
      split table, and both date formats
- [ ] `pytest tests/test_extraction.py -q` → passes against recorded fixtures, with
      no network
- [ ] A malformed response triggers exactly one repair attempt:
      `pytest tests/test_extraction.py -k repair -q` → passes
- [ ] `pytest tests/test_confidence.py -k quote -q` → passes; an unverifiable quote
      lowers confidence
- [ ] `pytest tests/test_crm_writer.py -k idempotent -q` → passes; writing the same
      extraction twice produces one record
- [ ] `pytest tests/test_crm_writer.py -k blocking -q` → passes; an uncertain NMI
      writes nothing
- [ ] `curl -s -X POST localhost:8000/documents -F document_type=electricity_bill -F file=@... -o /dev/null -w '%{http_code}'` → `202`
- [ ] `curl -s localhost:8000/review | jq '.items | length'` → a number, not a 501
- [ ] `psql "$VOLTDESK_DATABASE_URL" -c "SELECT count(*) FROM app.model_calls"` →
      one row per model call made, including failures
- [ ] `grep -rn --include="*.py" -A1 "raise NotImplementedError" voltdesk/ | grep "Phase 2"` → no output

## Known traps

**The NMI redaction bug (step 0).** It will silently ruin everything downstream.

**"Absent" is not "unsure".** `value=None, confidence=0.0` means the document does not
state the field. A low-confidence guess is a value with a low confidence. Collapsing
these makes the review queue useless.

**`extra="forbid"` means a single invented field fails the whole extraction.** That is
deliberate (ADR-0003). Budget for repair attempts; do not loosen the contract.

**Quoted email history.** A five-message thread parsed naively contains the first
message five times, and token cost scales quadratically. Deduplicate quoted blocks
before extraction.

**Bill tables split across pages.** The tariff table continues on page 2 without
repeating its header. A page-at-a-time parser produces headerless rows.

**Date formats.** `03/04/2026` is ambiguous and the corpus contains both conventions
on purpose. Use surrounding context (the billing period must be internally
consistent), and lower confidence when it genuinely cannot be resolved. Do not pick
one convention and hope.

**Idempotency comes from document facts.** The external key is derived from NMI plus
billing period, never from a UUID you generated. A UUID-based key creates a new CRM
record on every reprocess.

**Do not build a review UI.** Out of scope (`docs/SCOPE.md`). The API is the interface.

## Report back

Append to `PROGRESS.md`:

```markdown
## Phase 2 — report

**Status:** complete | partial

**Implemented:** <files, one line each>

**Acceptance checklist:** <N/M passing; name every failure>

**Contract changes:** <fields added, with the ADR number — or "none">

**ADRs added:** <numbers and one-line summaries>

**TODO(verify) resolved:** <which, and what you found>
**TODO(verify) still open:** <which, and why>

**Traps I hit that PHASE_3.md should know about:** <...>

**What I would tell the next model:** <...>
```
