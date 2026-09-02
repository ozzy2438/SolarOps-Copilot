"""Model pricing and cost computation. Owned by Phase 1."""

from __future__ import annotations

import pytest

from voltdesk.contracts.common import Provider
from voltdesk.llm.pricing import (
    ANTHROPIC_MODELS,
    DEFAULT_MODEL_ID,
    OPENAI_MODELS,
    UnknownModelError,
    assert_verified,
    compute_cost_usd,
    get_price,
)


def test_default_model_has_a_price() -> None:
    price = get_price(DEFAULT_MODEL_ID)
    assert price.provider == Provider.OPENAI
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


@pytest.mark.parametrize(
    ("model_id", "input_price", "output_price"),
    [("gpt-4o", 2.50, 10.00), ("gpt-4o-mini", 0.15, 0.60)],
)
def test_openai_price_is_verified(
    model_id: str, input_price: float, output_price: float
) -> None:
    price = OPENAI_MODELS[model_id]
    assert price.input_usd_per_mtok == input_price
    assert price.output_usd_per_mtok == output_price
    assert price.context_window == 128_000
    assert price.verified is True
    assert_verified(model_id)


def test_anthropic_cache_tokens_use_published_multipliers() -> None:
    cost = compute_cost_usd(
        "claude-opus-5",
        1_000_000,
        1_000_000,
        cache_read_input_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
    )
    assert cost == pytest.approx(5.00 + 25.00 + 0.50 + 6.25)


def test_verified_price_passes_the_guard() -> None:
    assert_verified("claude-opus-5")
