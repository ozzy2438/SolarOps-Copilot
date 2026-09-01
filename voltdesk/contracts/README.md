# Contracts

Every object that crosses a boundary in VoltDesk is defined here. A boundary is any
of: the FastAPI surface, a call to an LLM provider, a write to EspoCRM, a row in
PostgreSQL, or a file on disk that another phase reads.

## The rule

**Later phases may add fields. They may never rename or remove one.**

This is not a style preference. Phase 2 writes extraction records, Phase 3 writes
retrieval records, and Phase 4 reads both to compute metrics. Phase 4 cannot re-run
Phase 2's work; it only has the rows. A field renamed in Phase 3 silently produces
`None` in Phase 4's aggregation and the resulting numbers are wrong without anything
raising an error.

Concretely:

- Adding an optional field with a default: allowed, no coordination needed.
- Adding a required field: allowed only if you also write a migration that backfills
  it, and only if you say so in your phase report.
- Renaming a field: not allowed. Add the new field, populate both, and record an ADR
  in `docs/DECISIONS.md` proposing the old one for removal in a later phase.
- Removing a field: not allowed in phases 2-4.
- Adding an enum member: allowed. Removing one: not allowed.
- Changing a field's type: not allowed. Widening `X` to `X | None` is a type change.

## Why `extra="forbid"`

`StrictModel` forbids unknown keys. When a model hallucinates a plausible-looking
field, we want a `ValidationError` we can catch, count, and feed into the schema
repair loop — not a quietly dropped key that makes a bad extraction look clean. The
audit log's `schema_invalid` outcome exists to count exactly this.

## Why every extracted value is wrapped

`ExtractedField[T]` carries `value`, `confidence`, `source_quote`, and `source_page`.
Nothing in this system writes a bare extracted value anywhere. The confidence band
policy in `docs/GUARDRAILS.md` — which decides whether a field auto-writes to the CRM
or goes to a human — is only expressible because the confidence travels with the value.

A consequence worth stating: `value=None, confidence=0.0` means *the document does not
state this*. It does not mean *the model was unsure*. An unsure model returns its best
guess with a low confidence. Phase 2 must preserve that distinction; the review queue's
`reason` text depends on it.

## JSON Schema exports

`schemas/*.json` are generated from these models by `scripts/export_schemas.py` and are
committed. They are consumed by the extraction prompts (Phase 2) and by anything outside
Python that needs to know the shape.

They are generated artefacts. Never hand-edit one. `make schemas` regenerates them and
`python scripts/export_schemas.py --check` fails if the committed files have drifted
from the models — that check runs in `make verify`, so a contract change with stale
schemas fails before it reaches a review.

To add a contract to the export set, append it to `EXPORTED_CONTRACTS` in
`voltdesk/contracts/__init__.py`.
