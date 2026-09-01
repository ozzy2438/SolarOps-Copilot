# Phase 3 — Knowledge retrieval

## Objective

Make the second capability real. A staff member asks a technical or compliance
question and gets an answer grounded in the company's own material, with citations
that can be checked — or an explicit refusal when the evidence is not there. You
build corpus ingestion, chunking, embeddings, hybrid retrieval, citation-grounded
synthesis and the abstention scorer. You do not touch document intake, routing or
evaluation.

The abstention half is not a fallback. Staff use these answers to make compliance
decisions, and a confident wrong answer about an export limit is worse than "I don't
have evidence for that". Build for that first.

## Files you create or modify

Create:

- `voltdesk/ingestion/corpus.py`, `chunking.py`, `embeddings.py` (implement)
- `voltdesk/retrieval/search.py`, `synthesis.py`, `abstention.py` (implement)
- `scripts/ingest_corpus.py` (new — the CLI that loads the corpus)
- `tests/test_chunking.py`, `test_retrieval.py`, `test_synthesis.py`,
  `test_abstention.py`
- `tests/fixtures/corpus/` — a handful of small real documents for tests

Modify:

- `voltdesk/api/routes/qa.py` — replace the 501s
- `tests/test_phase3_stubs.py` — replace each stub test with a real one, do not delete
- `migrations/0006_*.sql` or later — **only** if you need schema. Phase 2 used
  `0005_document_bytes.sql` for inbound file bytes. Set the vector dimension in a
  new migration; do not edit `0003`.
- `docs/DATA_SOURCES.md` — fill in the source table as you verify each entry
- `PROGRESS.md`, `docs/DECISIONS.md`

**Do not touch:**

`voltdesk/contracts/` (add optional fields only, with an ADR) · `voltdesk/llm/` ·
`voltdesk/audit/` · `voltdesk/crm/` · `voltdesk/parsers/` · `voltdesk/extraction/` ·
`voltdesk/review/` · `voltdesk/synthetic/` · `voltdesk/routing/` ·
`voltdesk/evaluation/` · `migrations/0001`–`0004` · `docs/SCOPE.md` · `schemas/`.

You may *use* `voltdesk/parsers/` to read corpus PDFs. Do not modify them.

## Contracts you consume and produce

**Consume:** `ParsedDocument` (Phase 2), `RetrievalQuery`, `CorpusSource`, `Settings`,
`CompletionRequest`/`CompletionResponse`.

**Produce:** `Chunk`, `RetrievedChunk`, `Citation`, `RetrievalAnswer`,
`AbstentionReason`.

## Implementation steps, in order

**Step 0 — verify the sources before you ingest anything.** Every row in
`docs/DATA_SOURCES.md` Tier A is an open `TODO(verify)`. For each: confirm the current
URL, record the licence, record the retrieval date. **A document whose licence you
could not verify is not ingested** — leave its TODO open and say so in your report.
`vec.corpus_documents.licence` is nullable, but a NULL there means the document should
not have been ingested. This is the one failure in this project a later phase cannot
fix.

Retrieval date matters: rebate programs and connection guidelines get revised, and an
answer cited from a superseded version is wrong in a way that looks right.

**Step 1 — ingestion pipeline.** `ingest_path()`: parse → chunk → embed → store, with
`source_url`, `licence` and `retrieved_at` recorded per document. Idempotent by
`sha256`; re-ingesting the same file must not duplicate chunks.

**Step 2 — chunking.** These are standards, datasheets and connection guidelines.
Their meaning lives in numbered clauses and tables. A fixed-size character window cuts
a clause in half and makes the retrieved chunk uncitable. Chunk on structure — heading
path, clause boundary — and populate `section_path`, because the citation shows it to
the reader. Keep tables intact even when that means an oversized chunk.

**Step 3 — embeddings.** Choose the model. **Record the choice as an ADR** with the
reasoning. Add a migration setting `vec.embeddings.embedding` to that model's
dimension — `0003` has a placeholder of 1536 and a TODO saying so. Store
`embedding_model_id` on every row: a corpus embedded with two models is silently
unusable and recording the model is the only defence.

**Step 4 — hybrid retrieval.** Vector similarity **and** lexical search over
`vec.chunks` (the GIN index exists). Vector search alone under-retrieves here: staff
ask about clause numbers, standard identifiers and model numbers, which are exact-match
lookups that embeddings blur. Return `RetrievedChunk` carrying the score you actually
used — the abstention scorer reads it.

**Step 5 — synthesis with verified citations.** Generate the answer through
`LLMClient`. Then **verify**: every citation's `quote` must appear verbatim in the
chunk it names. A paraphrased quote is an unverifiable citation, and an unverifiable
citation turns the answer into an abstention — not an answer with a warning. The
`RetrievalAnswer` validator will refuse to serialise an uncited answer anyway
(ADR-0012), so build for it rather than fighting it.

**Step 6 — abstention scorer.** `support_score` in [0,1], compared against
`VOLTDESK_ABSTENTION_THRESHOLD`. Below it, abstain **without making a model call** —
abstaining cheaply is a feature. Pick the `AbstentionReason` honestly; the user is
told it, so it must be true.

**Step 7 — wire up `/qa`.** Replace the 501s. An abstention is a **200**, not an
error: the system did its job.

## Acceptance criteria

- [ ] `make verify` → clean
- [ ] `python scripts/ingest_corpus.py --dry-run` → lists every document with its
      licence; **exits non-zero if any licence is missing**
- [ ] `python scripts/ingest_corpus.py` → prints chunks written; running it twice
      writes zero the second time (idempotent)
- [ ] `docker compose exec -T postgres psql -U voltdesk -d voltdesk -c "SELECT count(*) FROM vec.corpus_documents WHERE licence IS NULL"` → `0`
- [ ] `docker compose exec -T postgres psql -U voltdesk -d voltdesk -c "SELECT DISTINCT embedding_model_id FROM vec.embeddings"` → exactly one value
- [ ] `pytest tests/test_chunking.py -q` → passes; a numbered clause is never split
      and `section_path` is populated
- [ ] `pytest tests/test_retrieval.py -k lexical -q` → passes; an exact clause-number
      query retrieves the right chunk
- [ ] `pytest tests/test_synthesis.py -k verbatim -q` → passes; a paraphrased citation
      is rejected
- [ ] `pytest tests/test_abstention.py -q` → passes; an out-of-corpus question abstains
      **and makes no model call** (assert on the audit records)
- [ ] `curl -s -X POST localhost:8000/qa/ask -H 'content-type: application/json' -d '{"query_id":"q1","question":"<in-corpus question>"}' | jq '.citations | length'` → `>= 1`
- [ ] Same, with an out-of-corpus question → `.abstained == true` and HTTP `200`
- [ ] `grep -rn --include="*.py" -A1 "raise NotImplementedError" voltdesk/ | grep "Phase 3"` → no output

## Known traps

**Verify licences before ingesting, not after.** Unwinding an ingestion you had no
right to perform is not something a later phase can do for you.

**Fixed-size chunking will look fine and fail quietly.** The answers will be
plausible and the citations will point at half-clauses. Chunk on structure.

**Embedding dimension mismatch.** `0003` has a placeholder of 1536. If your model's
dimension differs and you do not migrate, inserts fail — which is the intended loud
failure. Do not "fix" it by truncating vectors.

**Pure vector search under-retrieves exact identifiers.** "AS/NZS 4777.2 clause 5.3"
and "Fronius Symo 20.0-3-M" are lookups, not semantic similarity. Hybrid, not vector.

**Do not let the model write its own citations from memory.** It must cite only from
the chunks it was given, and you must verify verbatim afterwards. This is the whole
credibility of the capability.

**Abstention must be cheap.** If `support_score` is below threshold, return without
calling a model. An expensive abstention discourages abstaining, and a system that is
reluctant to abstain is the failure mode this design exists to prevent.

**Never ingest a customer document into the corpus.** Tier A only. This is what makes
it structurally impossible for one customer's data to leak into another user's answer.

## Report back

Append to `PROGRESS.md`, same template as Phase 2, plus:

```markdown
**Embedding model chosen:** <model, dimension, ADR number, why>
**Corpus ingested:** <N documents, M chunks, per source>
**Sources verified:** <which> — **Sources still unverified:** <which, and why>
**Abstention rate on a smoke set:** <N/M, and whether that felt right>
```
