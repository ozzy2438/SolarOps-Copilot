"""Model identities and per-token prices.

Owned by: Phase 1. Fully implemented for Anthropic; OpenAI entries are marked
TODO(verify) and must be confirmed before any cost number derived from them is
published.

Cost is computed at call time and stored on the audit record. It is never
recomputed at read time: a price change must not silently rewrite history.
"""

from __future__ import annotations

from voltdesk.contracts.common import Provider, StrictModel


class ModelPrice(StrictModel):
    """USD per million tokens, as published by the provider."""

    provider: Provider
    model_id: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    context_window: int
    verified: bool = True
    note: str | None = None


#: Anthropic pricing and model identities, from the Anthropic API model table.
#: Model IDs are complete as written - never append a date suffix to them.
ANTHROPIC_MODELS: dict[str, ModelPrice] = {
    "claude-opus-5": ModelPrice(
        provider=Provider.ANTHROPIC,
        model_id="claude-opus-5",
        input_usd_per_mtok=5.00,
        output_usd_per_mtok=25.00,
        context_window=1_000_000,
    ),
    "claude-sonnet-5": ModelPrice(
        provider=Provider.ANTHROPIC,
        model_id="claude-sonnet-5",
        input_usd_per_mtok=2.00,
        output_usd_per_mtok=10.00,
        context_window=1_000_000,
    ),
    "claude-haiku-4-5": ModelPrice(
        provider=Provider.ANTHROPIC,
        model_id="claude-haiku-4-5",
        input_usd_per_mtok=1.00,
        output_usd_per_mtok=5.00,
        context_window=200_000,
    ),
}

#: OpenAI pricing was NOT verified during Phase 1.
#: TODO(verify): confirm both the model identifiers and the per-token prices against
#: https://platform.openai.com/docs/pricing before Phase 4 publishes any Claude-vs-GPT
#: cost comparison. Phase 4 must fail loudly rather than quote an unverified number -
#: see `assert_verified` below.
OPENAI_MODELS: dict[str, ModelPrice] = {
    "gpt-4o": ModelPrice(
        provider=Provider.OPENAI,
        model_id="gpt-4o",
        input_usd_per_mtok=0.0,
        output_usd_per_mtok=0.0,
        context_window=128_000,
        verified=False,
        note="TODO(verify): model id, prices and context window are placeholders.",
    ),
    "gpt-4o-mini": ModelPrice(
        provider=Provider.OPENAI,
        model_id="gpt-4o-mini",
        input_usd_per_mtok=0.0,
        output_usd_per_mtok=0.0,
        context_window=128_000,
        verified=False,
        note="TODO(verify): model id, prices and context window are placeholders.",
    ),
}

ALL_MODELS: dict[str, ModelPrice] = {**ANTHROPIC_MODELS, **OPENAI_MODELS}

#: What the router picks when nothing more specific applies. Opus 5 is the default
#: because Phase 1 has no measurements yet; Phase 4 replaces this with a task table
#: driven by the benchmark, and records the change as an ADR.
DEFAULT_MODEL_ID = "claude-opus-5"


class UnknownModelError(KeyError):
    """Raised rather than guessing a price for an unrecognised model id."""


class UnverifiedPriceError(RuntimeError):
    """Raised when a cost figure would be derived from an unverified price."""


def get_price(model_id: str) -> ModelPrice:
    try:
        return ALL_MODELS[model_id]
    except KeyError as exc:
        raise UnknownModelError(
            f"no price entry for model {model_id!r}; add it to voltdesk/llm/pricing.py "
            f"rather than assuming a price"
        ) from exc


def assert_verified(model_id: str) -> None:
    """Guard for anything that publishes a cost figure.

    Phase 4's benchmark calls this before writing a cost into a report.
    """
    price = get_price(model_id)
    if not price.verified:
        raise UnverifiedPriceError(
            f"pricing for {model_id!r} is a Phase 1 placeholder ({price.note}); "
            f"verify it against the provider's published pricing before publishing a cost"
        )


def compute_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Cost of one call. Cache reads are billed at the input rate here.

    TODO(verify): Anthropic bills cache reads at a discount to the base input rate.
    Until that multiplier is confirmed, this over-estimates cached calls, which is the
    safe direction for a cost ceiling but wrong for a cost report. Phase 4 owns fixing it.
    """
    price = get_price(model_id)
    return (
        input_tokens * price.input_usd_per_mtok / 1_000_000
        + output_tokens * price.output_usd_per_mtok / 1_000_000
    )
