"""Health and readiness.

Owned by: Phase 1. Fully implemented.

Two endpoints, because they answer different questions:
  /health/live  - is the process up? Never touches a dependency.
  /health/ready - can it actually serve? Checks every dependency and says which failed.

A readiness probe that hides which dependency is down turns a two-minute diagnosis
into a twenty-minute one, so this one names them.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from voltdesk.config import get_settings
from voltdesk.crm.client import EspoCrmClient
from voltdesk.db.session import get_engine
from voltdesk.llm.registry import ProviderRegistry

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    """Liveness. No dependency is consulted."""
    return {"status": "ok"}


@router.get("/ready")
def ready(response: Response) -> dict[str, Any]:
    """Readiness. Degraded is reported as 503 with per-dependency detail."""
    checks: dict[str, Any] = {}

    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001 - the point is to report, not to raise
        checks["database"] = {"ok": False, "error": str(exc)[:200]}

    try:
        import redis

        redis.Redis.from_url(get_settings().redis_url).ping()
        checks["redis"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = {"ok": False, "error": str(exc)[:200]}

    try:
        with EspoCrmClient() as crm:
            checks["espocrm"] = {"ok": crm.health()}
    except Exception as exc:  # noqa: BLE001
        checks["espocrm"] = {"ok": False, "error": str(exc)[:200]}

    registry = ProviderRegistry()
    checks["llm_providers"] = {
        "usable": [str(p) for p in registry.usable_providers()],
        # No key configured is a valid local state, not an outage. Only report not-ok
        # when neither provider can be reached at all.
        "ok": bool(registry.usable_providers()),
    }

    healthy = all(
        check.get("ok", False) for check in checks.values() if isinstance(check, dict)
    )
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if healthy else "degraded", "checks": checks}
