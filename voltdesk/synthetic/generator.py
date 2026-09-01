"""Synthetic document generator.

Owned by: Phase 2. Specification is in voltdesk/synthetic/spec.py (Phase 1).
"""

from __future__ import annotations

from voltdesk.synthetic.spec import GeneratedDocument, GeneratorConfig


class SyntheticGenerator:
    """Deterministic generator. Same config -> same bytes."""

    def __init__(self, config: GeneratorConfig) -> None:
        self.config = config

    def generate(self) -> list[GeneratedDocument]:
        raise NotImplementedError(
            "SyntheticGenerator.generate is implemented in Phase 2 (docs/PHASE_2.md, step 1)"
        )
