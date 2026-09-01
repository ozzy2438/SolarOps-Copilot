"""Assign deliberate defects to a generated document.

Owned by: Phase 2. Defects are injected on purpose; see voltdesk/synthetic/spec.py.
"""

from __future__ import annotations

import random

from voltdesk.synthetic.spec import Defect, GeneratorConfig


def defects_for(
    rng: random.Random, config: GeneratorConfig, index: int, total: int
) -> list[Defect]:
    """Deterministic defect set. The first `defect_rate` fraction of each type
    carry at least one enabled defect; the rest are clean."""
    enabled = list(config.enabled_defects)
    if not enabled or total <= 0:
        return []
    cutoff = int(total * config.defect_rate)
    if index >= cutoff:
        return []
    primary = enabled[index % len(enabled)]
    chosen = [primary]
    # A second compatible defect on every third defective document, still seeded.
    if index % 3 == 0 and len(enabled) > 1:
        other = enabled[(index + 1) % len(enabled)]
        if other != primary:
            chosen.append(other)
    return chosen
