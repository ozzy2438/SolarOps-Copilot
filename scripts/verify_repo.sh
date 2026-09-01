#!/usr/bin/env bash
# Verify the repository is healthy. Every phase runs this before reporting done.
# Owned by Phase 1.
set -euo pipefail

echo "==> contracts import and export cleanly"
python -c "import voltdesk.contracts as c; print(f'  {len(c.EXPORTED_CONTRACTS)} contracts')"
python scripts/export_schemas.py --check

echo "==> lint"
ruff check voltdesk tests scripts

echo "==> types"
mypy voltdesk

echo "==> tests"
pytest -q

echo
echo "repo OK"
