"""Phase 2's stubs fail loudly and name their phase.

Owned by: Phase 1. These are the executable version of the handoff document.

When Phase 2 implements a component, its test here should be replaced with a real
test — not deleted. A disappearing test is indistinguishable from a forgotten one.
"""

from __future__ import annotations

import pytest

from voltdesk.contracts.common import DocumentType
from voltdesk.extraction import prompts
from voltdesk.extraction.confidence import calibrate, classify_for_write, verify_quote
from voltdesk.extraction.extractor import Extractor
from voltdesk.parsers import BillParser, EmailThreadParser, SiteNotesParser
from voltdesk.review.queue import ReviewQueue
from voltdesk.synthetic import GeneratorConfig, SyntheticGenerator

pytestmark = pytest.mark.phase2


@pytest.mark.parametrize("parser", [BillParser(), SiteNotesParser(), EmailThreadParser()])
def test_parsers_are_not_implemented(parser: object) -> None:
    with pytest.raises(NotImplementedError, match="Phase 2"):
        parser.parse("doc-1", b"", "f.pdf")  # type: ignore[attr-defined]


def test_extractor_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 2"):
        Extractor().extract(None)  # type: ignore[arg-type]


def test_prompts_are_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 2"):
        prompts.system_prompt_for(DocumentType.ELECTRICITY_BILL)
    with pytest.raises(NotImplementedError, match="Phase 2"):
        prompts.user_prompt_for(DocumentType.ELECTRICITY_BILL, "text")


def test_confidence_scoring_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 2"):
        verify_quote("q", None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError, match="Phase 2"):
        calibrate(None, None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError, match="Phase 2"):
        classify_for_write("nmi", 0.9)


def test_review_queue_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 2"):
        ReviewQueue().list_pending()


def test_synthetic_generator_is_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="Phase 2"):
        SyntheticGenerator(GeneratorConfig(seed=1)).generate()


def test_generator_config_is_reproducible_by_construction() -> None:
    """The spec itself IS implemented in Phase 1: same seed, same config."""
    assert GeneratorConfig(seed=42) == GeneratorConfig(seed=42)
    assert GeneratorConfig(seed=42) != GeneratorConfig(seed=43)
