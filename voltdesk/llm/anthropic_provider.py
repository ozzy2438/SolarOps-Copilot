"""Anthropic provider adapter.

Owned by: Phase 1. Fully implemented.

Notes on the current Anthropic API surface, because getting these wrong is a silent
quality regression rather than an error:

- Adaptive thinking (`thinking={"type": "adaptive"}`) is used only on the configured
  models that support it. Haiku 4.5 rejects adaptive thinking, so its benchmark path
  leaves thinking off instead of silently changing the token budget.
- `temperature` / `top_p` are not accepted on current models; do not add them.
- Assistant prefill is rejected; output shape is controlled with structured outputs.
- A safety refusal returns HTTP 200 with `stop_reason == "refusal"`, so `stop_reason`
  must be checked before reading content.
"""

from __future__ import annotations

import time
from typing import Any

from voltdesk.config import get_settings
from voltdesk.contracts.audit import TokenUsage
from voltdesk.contracts.common import CallOutcome, Provider
from voltdesk.llm.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
)

_ADAPTIVE_THINKING_MODELS = frozenset({"claude-opus-5", "claude-sonnet-5"})


class AnthropicProvider(LLMProvider):
    """Adapter over the official `anthropic` SDK."""

    provider = Provider.ANTHROPIC

    def __init__(self, client: Any | None = None) -> None:
        """`client` is injectable so unit tests can pass a recorded double; nothing
        here touches the network at construction time."""
        self._client = client
        self._settings = get_settings()

    def is_available(self) -> bool:
        return self._client is not None or self._settings.has_anthropic()

    def _get_client(self) -> Any:
        if self._client is None:
            import anthropic  # imported lazily: the package must import without the SDK

            client_options: dict[str, Any] = {
                "api_key": self._settings.anthropic_api_key.get_secret_value(),
                "timeout": self._settings.llm_timeout_seconds,
                "max_retries": self._settings.llm_max_retries,
            }
            workspace_id = self._settings.anthropic_workspace_id.get_secret_value().strip()
            if workspace_id:
                client_options["default_headers"] = {"anthropic-workspace-id": workspace_id}

            self._client = anthropic.Anthropic(
                **client_options,
            )
        return self._client

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        import anthropic

        client = self._get_client()

        kwargs: dict[str, Any] = {
            "model": request.model_id,
            "max_tokens": request.max_tokens,
            "messages": [{"role": "user", "content": request.user_content}],
        }
        thinking = _thinking_config(request.model_id)
        if thinking is not None:
            kwargs["thinking"] = thinking
        if request.system is not None:
            # A list with a cache_control breakpoint: the system prompt is stable
            # across calls, so caching it is free money. See docs/ARCHITECTURE.md.
            kwargs["system"] = [
                {
                    "type": "text",
                    "text": request.system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        if request.stop_sequences:
            kwargs["stop_sequences"] = request.stop_sequences
        if request.json_schema is not None:
            kwargs["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": _structured_output_schema(request.json_schema),
                }
            }

        started = time.perf_counter()
        try:
            response = client.messages.create(**kwargs)
        except anthropic.APITimeoutError as exc:
            raise ProviderError(
                f"anthropic timeout: {exc}", retryable=True, outcome=CallOutcome.TIMEOUT
            ) from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError(
                f"anthropic rate limited: {exc}",
                retryable=True,
                outcome=CallOutcome.PROVIDER_ERROR,
            ) from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(
                f"anthropic returned {exc.status_code}: {exc}",
                retryable=exc.status_code >= 500,
                outcome=CallOutcome.PROVIDER_ERROR,
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError(
                f"anthropic connection error: {exc}",
                retryable=True,
                outcome=CallOutcome.PROVIDER_ERROR,
            ) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            return CompletionResponse(
                provider=self.provider,
                model_id=request.model_id,
                text="",
                usage=_usage_from(response),
                latency_ms=latency_ms,
                outcome=CallOutcome.REFUSAL,
                stop_reason=stop_reason,
                refusal_category=getattr(details, "category", None),
                raw_response_id=getattr(response, "id", None),
            )

        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        return CompletionResponse(
            provider=self.provider,
            model_id=request.model_id,
            text=text,
            usage=_usage_from(response),
            latency_ms=latency_ms,
            outcome=CallOutcome.SUCCESS,
            stop_reason=stop_reason,
            raw_response_id=getattr(response, "id", None),
        )


def _structured_output_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Adapt provider-neutral JSON Schema to Anthropic's supported subset."""
    import anthropic

    return anthropic.transform_schema(schema)


def _thinking_config(model_id: str) -> dict[str, str] | None:
    """Return only thinking modes that the exact configured model supports."""
    if model_id in _ADAPTIVE_THINKING_MODELS:
        return {"type": "adaptive"}
    return None


def _usage_from(response: Any) -> TokenUsage:
    """Token counts come from the provider. We never estimate them."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return TokenUsage(input_tokens=0, output_tokens=0)
    return TokenUsage(
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )
