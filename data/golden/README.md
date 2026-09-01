# Golden set

150 evaluation records with human-established ground truth. Specification, metric
definitions and the task split are in `docs/EVALUATION.md`.

## File format

One JSON file per record in `records/`, named `<record_id>.json`, conforming to
`schemas/golden_record.json`.

```json
{
  "record_id": "bill-0001",
  "task_type": "bill_extraction",
  "input_path": "data/generated/bills/bill-0001.pdf",
  "expected": { "...": "..." },
  "ground_truth_source": "generator_seed",
  "notes": "optional"
}
```

## The `expected` object

**Extraction tasks** — dotted field path → expected value. Use the same paths the
contract uses. `null` means the document does not state the field, and a model that
returns a value for it is wrong.

**QA tasks** — three keys:

| Key | Meaning |
|---|---|
| `should_abstain` | Whether a correct system refuses to answer |
| `answer_contains` | Substrings that must appear in the answer (empty when abstaining) |
| `required_citation_chunk_ids` | Chunks the answer must cite (empty when abstaining) |

## Adding records

1. Copy the nearest worked example in `records/`.
2. Change the values. Do not change the key names.
3. Set `ground_truth_source` honestly — `generator_seed` only when the generator
   actually produced the document.
4. `python scripts/export_schemas.py --check` must still pass.

A record whose `ground_truth_source` is wrong corrupts the benchmark quietly, which
is worse than a missing record.
