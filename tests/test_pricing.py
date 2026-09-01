"""Model pricing and cost computation. Owned by Phase 1."""

from __future__ import annotations

import pytest

from voltdesk.contracts.common import Provider
from voltdesk.llm.pricing import (
    ANTHROPIC_MODELS,
    DEFAULT_MODEL_ID,
    UnknownModelError,
    UnverifiedPriceError,
    assert_verified,
    compute_cost_usd,
    get_price,
)


def test_default_model_has_a_price() -> None:
    price = get_price(DEFAULT_MODEL_ID)
    assert price.provider == Provider.ANTHROPIC
    assert price.input_usd_per_mtok > 0


def test_unknown_model_raises_rather_than_guessing() -> None:
    with pytest.raises(UnknownModelError):
        get_price("some-model-nobody-priced")


def test_cost_is_computed_from_the_published_rate() -> None:
    price = ANTHROPIC_MODELS["claude-opus-5"]
    cost = compute_cost_usd("claude-opus-5", 1_000_000, 1_000_000)
    assert cost == pytest.approx(price.input_usd_per_mtok + price.output_usd_per_mtok)


def test_anthropic_model_ids_carry_no_date_suffix() -> None:
    """Appending a date suffix to a current model id produces a 404 at call time."""
    for model_id in ANTHROPIC_MODELS:
        assert not model_id[-1].isdigit() or "-20" not in model_id


def test_unverified_openai_price_refuses_to_be_published() -> None:
    """Phase 4 must not publish a cost derived from a Phase 1 placeholder."""
    with pytest.raises(UnverifiedPriceError):
        assert_verified("gpt-4o")


def test_verified_price_passes_the_guard() -> None:
    assert_verified("claude-opus-5")
