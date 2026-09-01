# Data sources

Two tiers. The distinction is a deliberate engineering and privacy decision and must
survive to the final documentation — it is the answer to "is any of this real
customer data?" and the answer must be *no*.

## Tier A — real, publicly sourced

Used for the retrieval corpus and reference tables. Never contains personal
information.

| Source | Used for | Status |
|---|---|---|
| Clean Energy Council approved module list | Reference table; component validation | `TODO(verify)` — current URL and licence terms |
| Clean Energy Council approved inverter list | Reference table; component validation | `TODO(verify)` — current URL and licence terms |
| Manufacturer technical datasheets | Corpus; the real parsing test bed (real PDFs, real table layouts) | `TODO(verify)` — per-manufacturer redistribution terms |
| Distribution network embedded generation connection guidelines | Corpus; export limits, connection requirements | `TODO(verify)` — one per DNSP, terms differ |
| Regulator small-scale certificate methodology | Corpus; certificate calculations | `TODO(verify)` — current document name and version |
| State and federal rebate program documentation | Corpus; eligibility questions | `TODO(verify)` — programs change; record retrieval date |
| Public energy plan / tariff API data | Synthetic bill generation (real tariff structures) | `TODO(verify)` — API terms of use |
| Public half-hourly consumption and PV generation interval datasets | Synthetic bill generation (real consumption physics) | `TODO(verify)` — licence and attribution |

**Every row above is an open TODO.** Phase 1 did not verify any of these URLs or
licences, and deliberately did not invent them. This is the rule from the Phase 1
brief: where an external fact is uncertain, say so rather than write a plausible
detail that a later phase will build on.

### The rule for ingestion

`vec.corpus_documents.licence` is nullable in the schema, but a NULL there means the
document had no verified licence **and should not have been ingested**. Phase 3 owns
this check. Ingesting material VoltDesk has no right to redistribute is the one
failure in this project that a later phase cannot fix.

Record, per corpus document: source URL, licence, and retrieval date. The retrieval
date matters — rebate programs and connection guidelines are revised, and an answer
cited from a superseded version is wrong in a way that looks right.

## Tier B — synthetic

Only where personally identifiable information would otherwise appear:

- Customer and lead records
- Site assessment notes
- Email threads
- Electricity bill PDFs

### The rule

> Names, addresses, account numbers and contact details are fabricated.
> **The physics and the pricing are not.**

A synthetic bill with invented tariff rates teaches the parser nothing and makes the
extraction benchmark meaningless. Synthetic documents are built on top of real tariff
structures and real interval data from Tier A.

### Deliberate defects

The generator injects these on purpose (`voltdesk/synthetic/spec.py`). A corpus of
clean documents produces a parser that fails on the first real one.

- Skewed scans
- Missing text layer (forces the OCR path)
- Multi-page bills where a tariff table splits across a page break
- Inconsistent date formats — `DD/MM/YYYY` and `D Mon YYYY` in the same corpus
- Missing fields
- Two retailer layouts, so extraction cannot overfit to one template
- Handwritten-looking site notes
- Quoted email history (the trap that makes naive parsing scale quadratically)
- Low-contrast photocopies

### Reproducibility

`GeneratorConfig(seed=N)` fully determines the output. Same seed, same config, same
documents byte for byte. This is what makes the golden set reproducible and is why
ground truth for synthetic records carries `ground_truth_source='generator_seed'` —
the generator already knows every answer it constructed.

## What is never done

- Real customer documents are never committed to this repository.
- Real customer documents are never ingested into the retrieval corpus. The corpus is
  Tier A only, which is what makes it structurally impossible for a Q&A answer to leak
  one customer's data to another user.
- A synthetic record is never reported as real. `app.documents.tier` is a column, not
  a naming convention, precisely so this cannot happen by accident.
