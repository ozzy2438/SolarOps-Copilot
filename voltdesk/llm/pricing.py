"""Model identities and per-token prices.

Owned by: Phase 1 (table), Phase 4 (OpenAI verification and cache accounting).

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

#: OpenAI model identities, context windows and standard text-token prices verified
#: 2026-09-01 against the provider's model pages:
#: https://developers.openai.com/api/docs/models/gpt-4o
#: https://developers.openai.com/api/docs/models/gpt-4o-mini
OPENAI_MODELS: dict[str, ModelPrice] = {
    "gpt-4o": ModelPrice(
        provider=Provider.OPENAI,
        model_id="gpt-4o",
        input_usd_per_mtok=2.50,
        output_usd_per_mtok=10.00,
        context_window=128_000,
        verified=True,
        note="Verified 2026-09-01 against the official OpenAI GPT-4o model page.",
    ),
    "gpt-4o-mini": ModelPrice(
        provider=Provider.OPENAI,
        model_id="gpt-4o-mini",
        input_usd_per_mtok=0.15,
        output_usd_per_mtok=0.60,
        context_window=128_000,
        verified=True,
        note="Verified 2026-09-01 against the official OpenAI GPT-4o Mini model page.",
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


ANTHROPIC_CACHE_READ_MULTIPLIER = 0.10
ANTHROPIC_CACHE_CREATION_MULTIPLIER = 1.25


def compute_cost_usd(
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    *,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
) -> float:
    """Cost one call from provider-reported token categories.

    Anthropic documents cache reads at 0.1 times and five-minute cache writes at
    1.25 times the base input rate. Those multipliers were verified 2026-09-01 at
    https://platform.claude.com/docs/en/build-with-claude/prompt-caching.
    Other providers currently report zero for these Anthropic-specific categories.
    """
    price = get_price(model_id)
    input_cost = input_tokens * price.input_usd_per_mtok
    if price.provider == Provider.ANTHROPIC:
        input_cost += (
            cache_read_input_tokens
            * price.input_usd_per_mtok
            * ANTHROPIC_CACHE_READ_MULTIPLIER
        )
        input_cost += (
            cache_creation_input_tokens
            * price.input_usd_per_mtok
            * ANTHROPIC_CACHE_CREATION_MULTIPLIER
        )
    return (input_cost + output_tokens * price.output_usd_per_mtok) / 1_000_000
