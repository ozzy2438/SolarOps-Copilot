#!/usr/bin/env python3
"""Load the licence-reviewed Phase 3 corpus. Owned by Phase 3."""

from __future__ import annotations

import argparse
from pathlib import Path

from voltdesk.ingestion.corpus import ingest_path, licence_is_verified, load_manifest

DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "corpus"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    entries = load_manifest(args.path)
    missing = 0
    for entry in entries:
        verified = licence_is_verified(entry.licence)
        status = "verified" if verified else "MISSING"
        print(f"{entry.path.name}: licence={entry.licence or 'MISSING'} [{status}]")
        missing += int(not verified)
    if missing:
        print(f"refusing ingestion: {missing} document(s) lack a verified licence")
        return 2
    if args.dry_run:
        print(f"dry-run: {len(entries)} document(s), all licences verified")
        return 0

    total = 0
    for entry in entries:
        total += ingest_path(
            str(entry.path),
            entry.source,
            entry.title,
            source_url=entry.source_url,
            licence=entry.licence,
            retrieved_at=entry.retrieved_at,
            document_id=entry.document_id,
        )
    print(f"chunks written: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
