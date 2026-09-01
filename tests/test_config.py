"""Configuration. Owned by Phase 1."""

from __future__ import annotations

import pytest

from voltdesk.config import Settings, get_settings


def test_defaults_are_usable_without_any_environment() -> None:
    """The package must import and configure on a bare machine."""
    settings = Settings(_env_file=None)
    assert settings.env == "local"
    assert 0.0 <= settings.auto_write_confidence_threshold <= 1.0
    assert not settings.has_anthropic()
    assert not settings.has_openai()


def test_env_prefix_is_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLTDESK_ABSTENTION_THRESHOLD", "0.75")
    get_settings.cache_clear()
    assert get_settings().abstention_threshold == 0.75


def test_secrets_do_not_appear_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOLTDESK_ANTHROPIC_API_KEY", "sk-should-not-be-printed")
    get_settings.cache_clear()
    settings = get_settings()
    assert "sk-should-not-be-printed" not in repr(settings)
    assert settings.has_anthropic()
