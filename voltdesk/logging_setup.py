"""Structured logging.

Owned by: Phase 1. Fully implemented.

Every log line is JSON in non-local environments so that a log aggregator can read
them; local development gets a human-readable renderer. Call `configure_logging()`
once at process start - the FastAPI app factory and the RQ worker entry point both
do, and nothing else should.
"""

from __future__ import annotations

import logging
import sys

import structlog

from voltdesk.config import get_settings

#: Keys whose values are never written to a log line, at any level.
REDACTED_LOG_KEYS = frozenset(
    {"api_key", "authorization", "x-api-key", "password", "account_number", "email"}
)


def _scrub_secrets(
    _logger: object, _method: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    """Defence in depth: a secret that reaches a log line has already left the process."""
    for key in list(event_dict):
        if key.lower() in REDACTED_LOG_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging() -> None:
    """Idempotent. Safe to call more than once; later calls replace the configuration."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level, force=True)

    renderer: structlog.types.Processor
    if settings.env == "local":
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _scrub_secrets,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Module-level logger. Use the module's __name__."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
