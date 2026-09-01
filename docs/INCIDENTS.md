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
