# Phase 4 — Measurement and operations

## Objective

Turn a working system into an evidenced one. You build the golden set execution
harness, run the Claude vs GPT benchmark, replace the naive router with one driven by
what you measured, harden the guardrails against what you find, publish a metrics
page, run a live daily batch, and keep an honest incident log. This phase produces
the numbers the project is judged on, which is exactly why it must refuse to publish
a number it cannot stand behind.

## Files you create or modify

Create:

- `voltdesk/evaluation/runner.py`, `metrics.py` (implement)
- `voltdesk/routing/task_router.py` (new — the measured router)
- `voltdesk/batch.py` (new — the daily batch)
- `voltdesk/api/routes/metrics_page.py` (new — the rendered page)
- `data/golden/records/` — the full 150 records
- `docs/INCIDENTS.md` (new — the written incident log)
- `docs/RESULTS.md` (new — the benchmark writeup)
- `tests/test_metrics.py`, `test_runner.py`, `test_task_router.py`

Modify:

- `voltdesk/api/routes/admin.py` — replace the 501s
- `voltdesk/llm/pricing.py` — verify OpenAI entries, flip `verified`
- `tests/test_phase4_stubs.py` — replace each stub test, do not delete
- `PROGRESS.md`, `docs/DECISIONS.md`, `docs/GUARDRAILS.md` (hardening only)

**Do not touch:**

`voltdesk/contracts/` (add optional fields only, with an ADR) · `voltdesk/parsers/` ·
`voltdesk/extraction/` · `voltdesk/retrieval/` · `voltdesk/ingestion/` ·
`voltdesk/crm/client.py` · `voltdesk/audit/` · `migrations/0001`–`0004` ·
`docs/SCOPE.md` · `schemas/`.

If the benchmark shows an extraction or retrieval bug, **report it — do not fix it
here.** A measurement phase that edits the thing it is measuring has no baseline.
Write it up in `docs/RESULTS.md` with a proposed patch.

## Contracts you consume and produce

**Consume:** `GoldenRecord`, `ExtractionResult`, `RetrievalAnswer`, `AuditRecord`,
`ModelChoice`, `ReviewItem.corrections`.

**Produce:** `FieldScore`, `RecordResult`, `EvaluationResult`, `RoutingDecision`
(with `strategy=task_table`).

## Implementation steps, in order

**Step 0 — verify OpenAI pricing.** `OPENAI_MODELS` in `voltdesk/llm/pricing.py`
carries zeroed prices and `verified=False` (ADR-0008). `assert_verified()` raises
until you fix it, and `tests/test_pricing.py` pins that. Confirm the model identifiers
and per-token prices against the provider's published pricing, update the table, flip
the flag, update the test. **Until this is done you cannot publish a cost comparison** —
that gate is deliberate.

Also resolve the Anthropic cache-read multiplier TODO in `compute_cost_usd`; the
current code bills cache reads at the full input rate, which over-states cached calls.

**Step 1 — build the golden set to 150.** Per `docs/EVALUATION.md`: 50 bills, 30 site
assessments, 30 emails, 40 QA (25 answerable, **15 deliberately unanswerable**). Three
worked examples are committed as templates. Take extraction ground truth from the
generator's `ground_truth` where the document is synthetic, and from
`app.review_queue.corrections` where a human already corrected one. Set
`ground_truth_source` honestly — a wrong one corrupts the benchmark quietly.

Do not skip the 15 unanswerable QA cases. Without them abstention precision cannot be
measured and a system that never abstains scores perfectly.

**Step 2 — the runner.** `load_golden_set`, `run`, `run_benchmark`. Record the git SHA;
a run whose SHA is not in history is not reproducible and must not be published.
Results to `app.evaluation_runs`.

**Step 3 — metrics.** Implement every function in `metrics.py` **exactly** as
`docs/EVALUATION.md` defines it. Two specifics that are easy to get wrong:

- Precision and recall have **different denominators**. A model returning null for
  everything has *undefined* precision and *zero* recall. Do not report undefined as 0.
- Citation correctness is over **answered** records only, or abstaining maximises it.

**Step 4 — the benchmark.** Run the golden set across the Anthropic and OpenAI models,
per task type. Report accuracy, p50/p95 latency and cost per document. Write
`docs/RESULTS.md`: what you measured, what you found, and where the differences were
inside noise. **A difference you cannot distinguish from noise is not a finding** —
say so rather than ranking two models on a 2% gap over 50 records.

**Step 5 — the measured router.** Replace `StaticRouter` with `TaskRouter`, driven by
a task table you derived from step 4. `strategy=task_table`, and a `rationale` that
cites the measurement — the Phase 1 router says in words that it is a guess (ADR-0010);
yours must say what it is based on. Record the change as an ADR.

**Step 6 — re-derive the confidence threshold.** Build the coverage-accuracy curve and
set `VOLTDESK_AUTO_WRITE_CONFIDENCE_THRESHOLD` from it rather than from the 0.85
placeholder. If accuracy does **not** rise monotonically with confidence, the
confidences are not calibrated and the threshold cannot be set from them. **That
finding is more valuable than any headline accuracy number.** Report it prominently.

**Step 7 — guardrails hardening.** Address what the benchmark exposed: injection
attempts in the corpus, systematic over-confidence, a failure mode retry does not
cover. Update `docs/GUARDRAILS.md`. Note the honest claim already recorded there —
injection is mitigated and monitored, not solved. Do not upgrade that claim without
evidence.

**Step 8 — metrics page.** A rendered page over `app.model_calls` and
`app.evaluation_runs`: calls, cost, p95 latency, outcome mix, abstention rate,
review-queue depth, redaction coverage. Server-rendered HTML; no frontend framework
(`docs/SCOPE.md`).

**Step 9 — the daily batch.** `voltdesk/batch.py`, run by RQ on a schedule: process
the day's documents, run a reduced golden set, write an `EvaluationResult`, open an
`app.incidents` row on regression. This is what makes "runs unattended in production"
a fact rather than a claim.

**Step 10 — the incident log.** `docs/INCIDENTS.md`, one entry per real incident:
what happened, blast radius, root cause, remediation, related `call_id`s. Include the
ones you caused. A log with no entries is not evidence of reliability, it is evidence
of not looking.

## Acceptance criteria

- [ ] `make verify` → clean
- [ ] `python -c "from voltdesk.llm.pricing import assert_verified; assert_verified('gpt-4o')"` → no exception
- [ ] `python -c "from voltdesk.evaluation import load_golden_set; print(len(load_golden_set()))"` → `150`
- [ ] `python -c "from voltdesk.evaluation import load_golden_set as l; r=[x for x in l() if x.task_type.value=='knowledge_qa' and x.expected['should_abstain']]; print(len(r))"` → `15`
- [ ] `pytest tests/test_metrics.py -k precision_denominator -q` → passes; all-null
      predictions give undefined precision, not zero
- [ ] `python -m voltdesk.evaluation.runner --model claude-opus-5` → completes, writes
      one `app.evaluation_runs` row with a git SHA present in `git log`
- [ ] `python -m voltdesk.evaluation.runner --benchmark` → produces a row per model
- [ ] `docs/RESULTS.md` exists and states, for each headline comparison, whether the
      difference exceeds noise
- [ ] `pytest tests/test_task_router.py -q` → passes; every rationale cites a
      measurement, and none says "static default"
- [ ] `curl -s localhost:8000/metrics/page | grep -c "p95"` → `>= 1`
- [ ] `python -m voltdesk.batch --once` → completes and writes an evaluation run
- [ ] `docs/INCIDENTS.md` exists with at least one real entry, or states explicitly
      that no incident occurred and over what period
- [ ] `grep -rn --include="*.py" -A1 "raise NotImplementedError" voltdesk/ | grep "Phase 4"` → no output

## Known traps

**Publishing an unverified cost.** The single most damaging thing you can do here.
`assert_verified()` exists to stop it; do not work around it by hard-coding a number.

**Reporting noise as a finding.** 50 records per task is a small sample. A 2%
difference between two models is not a ranking. Report the interval or say the
comparison was inconclusive.

**Grading with a model without saying so.** If you use an LLM judge for QA answers,
that is a measurement instrument with its own error rate. Say so, and validate it
against a human-labelled subset.

**Fixing bugs you were measuring.** Tempting and it destroys the baseline. Report and
propose; let a follow-up apply.

**The circular-ground-truth trap.** Synthetic-only ground truth measures how well the
model reads documents this project wrote. The real-document minority in each
extraction split exists for that reason — keep it.

**An empty incident log.** Not a clean record; a sign of not looking. If nothing went
wrong, state the period observed.

**Changing the confidence threshold without the curve.** The whole point of step 6 is
that the threshold becomes measured rather than assumed.

## Report back

Append to `PROGRESS.md`, same template as Phase 2, plus:

```markdown
**Benchmark headline:** <model, task, metric, value — and the uncertainty>
**Router table adopted:** <task -> model, and the measurement behind each>
**Confidence threshold:** <old 0.85 -> new X, from the coverage-accuracy curve>
**Was confidence monotonic in accuracy?** <yes/no — if no, say so loudly>
**Incidents recorded:** <N, one line each>
**What the next person should not trust in these numbers:** <...>
```
