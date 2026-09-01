"""Generate JSON Schema exports from the Pydantic contracts.

Owned by: Phase 1. Fully implemented.

    python scripts/export_schemas.py           # write schemas/
    python scripts/export_schemas.py --check   # fail if committed files have drifted

The exports are committed because the extraction prompts (Phase 2) hand the schema to
the model. A hand-written copy of a schema drifts from the model silently and produces
extractions that validate against nothing. `--check` runs in `make verify` so the drift
is caught before review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from voltdesk.contracts import EXPORTED_CONTRACTS

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"


def _filename_for(model: type) -> str:
    """CamelCase -> snake_case.json, so filenames are stable and greppable."""
    name = model.__name__
    out: list[str] = []
    for index, char in enumerate(name):
        if char.isupper() and index > 0:
            out.append("_")
        out.append(char.lower())
    return "".join(out) + ".json"


def _render(model: type) -> str:
    schema = model.model_json_schema()  # type: ignore[attr-defined]
    # Sorted keys and a trailing newline: the file must be byte-stable across runs,
    # or --check reports drift that is only key ordering.
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit non-zero if any committed schema differs.",
    )
    args = parser.parse_args()

    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    drifted: list[str] = []
    written = 0

    for model in EXPORTED_CONTRACTS:
        path = SCHEMA_DIR / _filename_for(model)
        rendered = _render(model)
        if args.check:
            if not path.exists() or path.read_text() != rendered:
                drifted.append(path.name)
        else:
            path.write_text(rendered)
            written += 1

    if args.check:
        if drifted:
            print(
                "schema drift detected in: "
                + ", ".join(sorted(drifted))
                + "\nrun `make schemas` and commit the result",
                file=sys.stderr,
            )
            return 1
        print(f"schemas up to date ({len(EXPORTED_CONTRACTS)} contracts)")
        return 0

    print(f"wrote {written} schemas to {SCHEMA_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
