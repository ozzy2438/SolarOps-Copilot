"""Anthropic adapter request-shape checks. No live provider calls."""

from __future__ import annotations

from typing import Any

import anthropic
import pytest

from voltdesk.config import Settings
from voltdesk.llm import anthropic_provider


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
