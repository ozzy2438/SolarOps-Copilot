# Phase 4 benchmark results

## Measurement boundary

The published comparison uses two complete 150-record runs made on 2 September
2026 from the same committed source tree,
`f1f10ad03df810eaa2127167369044b5f943b59b`:

- `claude-haiku-4-5`: `eval-8325bd1c-879b-49a0-a858-b3d405377b8f`
- `gpt-4o-mini`: `eval-8d41a233-c32d-4318-892d-02c8c6f1ff00`

The user's model override is binding: `claude-opus-5` was not called. Prices were
verified and cost was captured by the audit path at call time. Latency is the remote
provider call observed from this development machine; it is not a service-level
objective and will change with provider load and network location.

An eight-record Haiku pilot ran first as
`eval-1b4d8748-0c5d-42fc-9a0a-543fe374266a`. It completed 8/8 without provider or
runtime failures. The evaluation attributed USD 0.046471 to the eight records. One
successful site request completed before a database interruption but was not
checkpointed, so it was repeated; the audit ledger for the pilot is therefore higher
at USD 0.052486. This is retained as operational evidence, not folded into the full
run's cost.

## Headline results

| Model | Exact match | Field precision | Field recall | p50 | p95 | Evaluation cost | Cost / record |
|---|---:|---:|---:|---:|---:|---:|---:|
| `claude-haiku-4-5` | 46/150 (30.67%) | 95.11% | 75.73% | 5,829 ms | 12,494 ms | $0.762898 | $0.005086 |
| `gpt-4o-mini` | 17/150 (11.33%) | 95.47% | 80.14% | 8,469 ms | 15,881 ms | $0.193353 | $0.001289 |

The Wilson 95% intervals for overall exact match are 23.85–38.45% for Haiku and
7.20–17.40% for GPT Mini. They do not overlap, so the overall exact-match difference
exceeds the uncertainty represented by this interval. That headline is dominated by
the site task and must not be read as “Haiku is better at every task.” GPT Mini has
higher overall field recall and costs about one quarter as much on this run.

The database stores costs at six decimal places per audited call, whereas the runner
sums the provider-returned values before the final database rounding. That explains
small ledger-versus-result differences. The Haiku audit total also includes the pilot
and its repeated orphan call. No cost was recomputed after the fact.

## Per-task results and uncertainty

| Task | Haiku exact | GPT Mini exact | Haiku / GPT recall | Haiku / GPT cost | Finding |
|---|---:|---:|---:|---:|---|
| Bill extraction (50) | 1/50 | 1/50 | 78.45% / 81.35% | $0.422129 / $0.106235 | Exact match is tied. A 1/50 interval is 0.35–10.50% for both, so no quality ranking is supported. GPT is the lower-cost choice and has slightly higher recall. |
| Email extraction (30) | 0/30 | 0/30 | 33.45% / 58.62% | $0.090839 / $0.035951 | Exact match is tied at zero; its interval is 0–11.35% for both. GPT has materially higher observed recall and lower cost, but this synthetic-only split does not establish external validity. |
| Knowledge QA (40) | 18/40 | 16/40 | n/a | $0.049539 / $0.005049 | Exact-match intervals overlap (Haiku 30.71–60.17%; GPT 26.35–55.40%). The two-record gap is inside noise, so GPT is selected on cost. |
| Site assessment (30) | 27/30 | 0/30 | 100.00% / 92.92% | $0.200392 / $0.046117 | Exact-match intervals do not overlap (Haiku 74.38–96.54%; GPT 0–11.35%). Haiku is the measured quality choice despite the higher cost. |

Haiku p95 latency by task was 19,964 ms (bill), 4,771 ms (email), 3,492 ms (QA)
and 10,437 ms (site). GPT Mini was 20,179 ms, 8,671 ms, 2,394 ms and 11,230 ms
respectively.

Both models found all 15 required abstentions, so abstention recall was 100%. Haiku
abstained on 37/40 QA records (precision 40.54%); GPT Mini abstained on 39/40
(precision 38.46%). Citation correctness was 100%, but its denominator was only the
three answers Haiku gave and the single answer GPT gave. The benchmark therefore
exposes severe over-abstention; the citation percentage alone is not evidence of a
generally useful answering system.

GPT Mini produced three bill record errors (`bill-0009`, `bill-0016`, `bill-0017`):
each remained invalid after the single schema-repair attempt. The provider calls were
successful, so this is a post-call contract-validation failure rather than provider
availability. The benchmark correctly retained the failures instead of changing the
extraction implementation being measured.

## Router adopted

| Task | Selected model | Measurement basis |
|---|---|---|
| Bill extraction | `gpt-4o-mini` | Exact match tied 1/50; GPT recall 81.35% versus 78.45%, at $0.106 versus $0.422. |
| Email extraction | `gpt-4o-mini` | Exact match tied 0/30; GPT recall 58.62% versus 33.45%, at lower cost. |
| Knowledge QA | `gpt-4o-mini` | 16/40 versus 18/40 is inside overlapping intervals; GPT task cost was $0.005 versus $0.050. |
| Site assessment | `claude-haiku-4-5` | 27/30 versus 0/30 exact, with non-overlapping intervals. |
| Schema repair | `gpt-4o-mini` | Both providers completed measured repair calls; GPT is the lower-cost measured fallback. |

Every runtime rationale cites both full run IDs. Provider fallback is limited to the
other model that was measured here and only when its credential is usable.

## Confidence coverage and accuracy

The curve below combines the fields the adopted router would have selected: GPT Mini
for bill and email records, Haiku for site records. QA has no confidence-bearing
extraction fields. There were 1,542 scored extraction fields.

| Confidence threshold | Selected fields | Coverage | Correct selected fields | Accuracy |
|---:|---:|---:|---:|---:|
| 0.00 | 1,299 | 84.24% | 1,128 | 86.84% |
| 0.50 | 1,148 | 74.45% | 1,083 | 94.34% |
| 0.80 | 1,127 | 73.09% | 1,077 | 95.56% |
| 0.85 | 1,122 | 72.76% | 1,075 | 95.81% |
| 0.90 | 1,122 | 72.76% | 1,075 | 95.81% |
| 0.95 | 1,118 | 72.50% | 1,074 | 96.06% |
| 1.00 | 828 | 53.70% | 787 | 95.05% |

**Accuracy is not monotonic:** it falls from 96.06% at 0.95 to 95.05% at 1.00.
Consequently the confidences are not calibrated and no new auto-write threshold can
be derived from this run. `VOLTDESK_AUTO_WRITE_CONFIDENCE_THRESHOLD` remains the
unpromoted 0.85 placeholder. Its 95.81% observed field accuracy is descriptive, not
a safety guarantee or evidence that the threshold is calibrated.

## What these numbers do not establish

- The 110 extraction records are all deterministic `generator_seed` examples. The
  40 QA records are human-labelled, but this checkout contains no human-labelled or
  reviewer-corrected bill/site extraction minority. This differs from the target
  composition in `docs/EVALUATION.md`; extraction generalisation to real customer
  documents is unmeasured.
- The corpus contained no labelled prompt-injection challenge cases. Structured
  output, quote checking and monitoring remain mitigations, but this benchmark did
  not measure injection resistance.
- Exact matching is deliberately harsh, while field precision can hide missing
  values. Both are reported because neither is sufficient alone.
- A single run per model does not measure provider variance across days. The Wilson
  intervals describe binomial record uncertainty, not network or model-version drift.
- QA citation correctness is based on very few answered questions because both
  models over-abstained.

These gaps are proposed follow-up work. They were not repaired during the measurement
phase because changing extraction, retrieval or the golden data after seeing results
would erase the baseline.
