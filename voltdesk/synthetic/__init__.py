"""Synthetic Tier B data. Spec owned by Phase 1; generator owned by Phase 2."""

from voltdesk.synthetic.generator import SyntheticGenerator
from voltdesk.synthetic.spec import Defect, GeneratedDocument, GeneratorConfig, RetailerLayout

__all__ = [
    "Defect",
    "GeneratedDocument",
    "GeneratorConfig",
    "RetailerLayout",
    "SyntheticGenerator",
]
