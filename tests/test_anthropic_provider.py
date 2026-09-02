"""Anthropic adapter request-shape checks. No live provider calls."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import anthropic
import pytest

from voltdesk.config import Settings
from voltdesk.llm import anthropic_provider
from voltdesk.llm.anthropic_provider import (
    _create_with_schema_fallback,
    _structured_output_schema,
    _thinking_config,
)


@pytest.mark.parametrize(
    ("workspace_id", "expected_headers"),
    [
        ("", None),
        (
            "wrkspc_test",
            {"anthropic-workspace-id": "wrkspc_test"},
        ),
    ],
)
def test_workspace_header_is_only_configured_when_present(
    monkeypatch: pytest.MonkeyPatch,
    workspace_id: str,
    expected_headers: dict[str, str] | None,
) -> None:
    settings = Settings(
        _env_file=None,
        anthropic_api_key="sk-ant-test",
        anthropic_workspace_id=workspace_id,
    )
    captured: dict[str, Any] = {}

    def fake_client(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(anthropic_provider, "get_settings", lambda: settings)
    monkeypatch.setattr(anthropic, "Anthropic", fake_client)

    provider = anthropic_provider.AnthropicProvider()
    provider._get_client()

    if expected_headers is None:
        assert "default_headers" not in captured
    else:
        assert captured["default_headers"] == expected_headers


def test_structured_output_schema_removes_unsupported_numeric_constraints() -> None:
    source = {
        "type": "object",
        "properties": {
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
            }
        },
        "required": ["confidence"],
    }

    transformed = _structured_output_schema(source)
    confidence = transformed["properties"]["confidence"]

    assert "minimum" not in confidence
    assert "maximum" not in confidence
    assert "minimum" in confidence["description"]
    assert "maximum" in confidence["description"]
    assert transformed["additionalProperties"] is False
    assert source["properties"]["confidence"]["minimum"] == 0.0


def test_thinking_configuration_matches_model_capability() -> None:
    assert _thinking_config("claude-haiku-4-5") is None
    assert _thinking_config("claude-opus-5") == {"type": "adaptive"}
    assert _thinking_config("claude-sonnet-5") == {"type": "adaptive"}


def test_oversized_grammar_retries_once_without_output_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeStatusError(Exception):
        status_code = 400

    calls: list[dict[str, Any]] = []

    def create(**kwargs: Any) -> str:
        calls.append(kwargs)
        if len(calls) == 1:
            raise FakeStatusError("The compiled grammar is too large")
        return "ok"

    monkeypatch.setattr(anthropic, "APIStatusError", FakeStatusError)
    client = SimpleNamespace(messages=SimpleNamespace(create=create))

    result = _create_with_schema_fallback(
        client,
        {
            "model": "claude-haiku-4-5",
            "messages": [],
            "output_config": {"format": {"type": "json_schema", "schema": {}}},
        },
    )

    assert result == "ok"
    assert "output_config" in calls[0]
    assert "output_config" not in calls[1]
