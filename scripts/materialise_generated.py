"""Materialise the deterministic synthetic documents used by the golden set.

The generated inputs are deliberately ignored by git: they are reproducible Tier B
artefacts, not source data.  Golden records reference these files by path, so a
checkout must materialise them before the records can be loaded.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from voltdesk.synthetic import GeneratorConfig, SyntheticGenerator

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = REPO_ROOT / "data/generated"
GENERATOR_SEED = 7
GENERATOR_COUNTS = {
    "bill_count": 50,
    "site_assessment_count": 30,
    "email_thread_count": 30,
}
EXPECTED_DOCUMENT_TYPES = {
    "electricity_bill": 50,
    "site_assessment": 30,
    "email_thread": 30,
}


def materialise(output_dir: Path = GENERATED_DIR) -> list[Path]:
    """Generate and verify every input artefact required by the golden set."""
    destination = output_dir.resolve()
    config = GeneratorConfig(
        seed=GENERATOR_SEED,
        output_dir=str(destination),
        **GENERATOR_COUNTS,
    )
    documents = SyntheticGenerator(config).generate()
    counts = Counter(document.document_type for document in documents)
    if counts != EXPECTED_DOCUMENT_TYPES:
        raise RuntimeError(
            f"unexpected generated document split: {dict(counts)}; "
            f"expected {EXPECTED_DOCUMENT_TYPES}"
        )

    paths = [Path(document.path).resolve() for document in documents]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        rendered = ", ".join(str(path) for path in missing)
        raise RuntimeError(f"generator did not materialise required documents: {rendered}")
    return paths


def main() -> int:
    paths = materialise()
    print(f"materialised generated documents: {len(paths)}")
    print("split: 50 bills, 30 site assessments, 30 emails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
