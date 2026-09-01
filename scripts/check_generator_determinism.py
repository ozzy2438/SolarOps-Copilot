#!/usr/bin/env python3
"""Fail if SyntheticGenerator is not deterministic for a fixed seed.

Owned by: Phase 2. Prints `deterministic: OK` on success so the Phase 2
acceptance checklist can grep a single token.
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

from voltdesk.synthetic import GeneratorConfig, SyntheticGenerator


def _fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> int:
    with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
        a = Path(first)
        b = Path(second)
        # Small counts keep the check cheap; seed is what must determine bytes.
        counts = {"bill_count": 4, "site_assessment_count": 3, "email_thread_count": 3}
        config_a = GeneratorConfig(seed=7, **counts)
        config_b = GeneratorConfig(seed=7, **counts)
        SyntheticGenerator(config_a.model_copy(update={"output_dir": str(a)})).generate()
        SyntheticGenerator(config_b.model_copy(update={"output_dir": str(b)})).generate()
        if _fingerprint(a) != _fingerprint(b):
            print("deterministic: FAIL", file=sys.stderr)
            return 1
    print("deterministic: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
