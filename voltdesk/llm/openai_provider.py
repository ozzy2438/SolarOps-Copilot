"""OpenAI provider adapter.

Owned by: Phase 1. Implemented against the official `openai` SDK's chat completions
surface.

TODO(verify): this adapter was written without a live OpenAI credential in Phase 1.
Two things must be confirmed by Phase 4 before any benchmark number derived from it
is published:
  1. the model identifiers in voltdesk/llm/pricing.py (OPENAI_MODELS),
  2. the exact structured-output parameter shape for the models actually used.
The parameter used below (`response_format` with a `json_schema`) is the documented
mechanism, but the per-model support matrix was not verified here.
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


class OpenAIProvider(LLMProvider):
    """Adapter over the official `openai` SDK."""

    provider = Provider.OPENAI

    def __init__(self, client: Any | None = None) -> None:
        self._client = client
        self._settings = get_settings()

    def is_available(self) -> bool:
        return self._client is not None or self._settings.has_openai()

    def _get_client(self) -> Any:
        if self._client is None:
            import openai

            self._client = openai.OpenAI(
                api_key=self._settings.openai_api_key.get_secret_value(),
                timeout=self._settings.llm_timeout_seconds,
                max_retries=self._settings.llm_max_retries,
            )
        return self._client

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        import openai

        client = self._get_client()

        messages: list[dict[str, str]] = []
        if request.system is not None:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.user_content})

        kwargs: dict[str, Any] = {
            "model": request.model_id,
            "messages": messages,
            "max_tokens": request.max_tokens,
        }
        if request.stop_sequences:
            kwargs["stop"] = request.stop_sequences
        if request.json_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "voltdesk_extraction",
                    "strict": True,
                    "schema": request.json_schema,
                },
            }

        started = time.perf_counter()
        try:
            response = client.chat.completions.create(**kwargs)
        except openai.APITimeoutError as exc:
            raise ProviderError(
                f"openai timeout: {exc}", retryable=True, outcome=CallOutcome.TIMEOUT
            ) from exc
        except openai.RateLimitError as exc:
            raise ProviderError(
                f"openai rate limited: {exc}",
                retryable=True,
                outcome=CallOutcome.PROVIDER_ERROR,
            ) from exc
        except openai.APIStatusError as exc:
            raise ProviderError(
                f"openai returned {exc.status_code}: {exc}",
                retryable=exc.status_code >= 500,
                outcome=CallOutcome.PROVIDER_ERROR,
            ) from exc
        except openai.APIConnectionError as exc:
            raise ProviderError(
                f"openai connection error: {exc}",
                retryable=True,
                outcome=CallOutcome.PROVIDER_ERROR,
            ) from exc
        latency_ms = int((time.perf_counter() - started) * 1000)

        choice = response.choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        message = choice.message
        refusal = getattr(message, "refusal", None)
        if refusal:
            return CompletionResponse(
                provider=self.provider,
                model_id=request.model_id,
                text="",
                usage=_usage_from(response),
                latency_ms=latency_ms,
                outcome=CallOutcome.REFUSAL,
                stop_reason=finish_reason,
                refusal_category=None,
                raw_response_id=getattr(response, "id", None),
            )

        return CompletionResponse(
            provider=self.provider,
            model_id=request.model_id,
            text=message.content or "",
            usage=_usage_from(response),
            latency_ms=latency_ms,
            outcome=CallOutcome.SUCCESS,
            stop_reason=finish_reason,
            raw_response_id=getattr(response, "id", None),
        )


def _usage_from(response: Any) -> TokenUsage:
    """OpenAI names these prompt_tokens / completion_tokens; normalise to our shape."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return TokenUsage(input_tokens=0, output_tokens=0)
    return TokenUsage(
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
    )
