# Evaluation

The golden set is what makes this a measured system rather than a demo. Phase 4 owns
running it; Phase 1 owns its specification, and the definitions below are binding — a
metric computed differently from its written definition makes the whole report
unreadable.

## The golden set: 150 records

| Task | Records | Ground truth source |
|---|---|---|
| `bill_extraction` | 50 | 35 `generator_seed`, 15 `human_labelled` (real Tier A datasheets and public sample bills) |
| `site_assessment_extraction` | 30 | 25 `generator_seed`, 5 `human_labelled` |
| `email_extraction` | 30 | `generator_seed` |
| `knowledge_qa` | 40 | `human_labelled` — 25 answerable, **15 deliberately unanswerable** |

The 15 unanswerable questions are the point of the QA split. Without cases that
*should* be refused, abstention precision cannot be measured and a system that never
abstains scores perfectly.

### How ground truth is established

- **`generator_seed`** — the synthetic generator constructed the document and knows
  every value it wrote. Free, exact, and reproducible from the seed.
- **`human_labelled`** — a person read the document and recorded the fields. Used for
  real Tier A documents, where no generator knows the answer.
- **`reviewer_correction`** — a correction made in the review queue, promoted into the
  golden set. This is the channel that lets the golden set grow from production use;
  `app.review_queue.corrections` is retained for exactly this.

Synthetic-only ground truth would be circular — it would measure how well the model
reads documents this project wrote. Hence the real-document minority in the extraction
splits.

## Metric definitions

### Field-level precision and recall

Per field, per record. Let a field be *predicted present* when the model returned a
non-null `value`, and *expected present* when ground truth has a value.

```
precision = correct predictions / predicted present
recall    = correct predictions / expected present
```

**The denominators differ, and that matters.** A model that returns null for
everything has *undefined* precision and *zero* recall. The implementation must not
paper over undefined precision with a zero — report it as undefined.

A prediction is *correct* when it is predicted present, expected present, and the
values match under the field's comparison rule:

- Numbers: exact after rounding to the field's natural precision (cents for money,
  1 kWh for consumption).
- Dates: exact. A date parsed from the wrong format is wrong, not close.
- Strings: normalised — case-folded, whitespace-collapsed, punctuation-stripped.
- Enums: exact.
- `None` vs `None`: counted as correct in neither numerator nor denominator. Correctly
  recognising an absent field is good behaviour but it is not a retrieval of anything.

### Exact-match rate

Fraction of records where **every** field is correct. Harsh on purpose: it is the
closest proxy for "this document needed no human at all".

### Citation correctness

For QA records only. A citation is correct when:

1. `chunk_id` is in the record's `required_citation_chunk_ids`, **and**
2. `quote` appears verbatim in that chunk.

```
citation_correctness = records with all citations correct / answered records
```

Note the denominator: **answered** records. Abstentions are scored separately —
otherwise abstaining maximises this metric.

### Abstention precision and recall

Over the QA split, where each record has `should_abstain`:

```
abstention_precision = correctly abstained / total abstained
abstention_recall    = correctly abstained / total that should have been abstained
```

Both are needed. Precision alone rewards a system that answers everything and
abstains once, correctly. Recall alone rewards a system that abstains on everything.

### Coverage-accuracy curve

The curve that answers the only question the business actually has: *at what
confidence can a field be written without a human, and what fraction of fields clear
that bar?*

For thresholds `t` in `0.00, 0.05, ..., 1.00`:

```
coverage(t) = fields with confidence >= t / total fields
accuracy(t) = correct fields with confidence >= t / fields with confidence >= t
```

A well-calibrated system's accuracy rises monotonically as `t` rises. If it does not,
the confidences are not calibrated and `VOLTDESK_AUTO_WRITE_CONFIDENCE_THRESHOLD`
cannot be set from them — that finding is more valuable than any headline accuracy
number, and Phase 4 must report it if it appears.

### Latency

`p50` and `p95` per task type, in milliseconds, measured at `LLMClient.complete()` —
provider call only, excluding parsing. p95 is reported because the mean hides the
tail, and the tail is what a queue backs up behind.

### Cost

```
cost_per_document_usd = total cost of every call for that document / documents
```

Includes repair attempts and retries. A model that is cheap per call but needs two
repairs is not cheap, and reporting only the successful call would hide that.

**Cost figures may only be published for models whose price is verified.** Phase 4
must call `voltdesk.llm.pricing.assert_verified()` before writing any cost into a
report — OpenAI prices are Phase 1 placeholders (ADR-0008).

## Golden set on disk

```
data/golden/
  README.md
  records/
    bill-0001.json
    site-0001.json
    email-0001.json
    qa-0001.json
```

One JSON file per record, filename stem equal to `record_id`, conforming to
`schemas/golden_record.json`. Input artefacts referenced by repo-relative path in
`input_path`.

Three fully worked examples are committed in `data/golden/records/`. They are the
template — a new record is a copy of the nearest one with the values changed.

## Running it

```bash
python -m voltdesk.evaluation.runner --model claude-haiku-4-5
python -m voltdesk.evaluation.runner --model gpt-4o-mini
python -m voltdesk.evaluation.runner --benchmark
```

The Phase 4 operator explicitly excluded `claude-opus-5`; `--benchmark` therefore
runs only `claude-haiku-4-5` and `gpt-4o-mini`.

Every run records the git SHA it ran at. Results land in `app.evaluation_runs`. A run
whose SHA is not in the repository's history is not reproducible and should not be
published.
