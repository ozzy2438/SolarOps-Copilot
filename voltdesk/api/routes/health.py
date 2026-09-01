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
    """Readiness. A configured dependency that is failing gives 503 with detail."""
    settings = get_settings()
    checks: dict[str, Any] = {}

    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        checks["database"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001 - the point is to report, not to raise
        checks["database"] = {"ok": False, "error": str(exc)[:200]}

    try:
        import redis

        redis.Redis.from_url(settings.redis_url).ping()
        checks["redis"] = {"ok": True}
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = {"ok": False, "error": str(exc)[:200]}

    try:
        with EspoCrmClient() as crm:
            crm_health = crm.health()
        checks["espocrm"] = {
            "ok": crm_health.ok,
            "configured": crm_health.configured,
            "reachable": crm_health.reachable,
            "detail": crm_health.detail,
        }
    except Exception as exc:  # noqa: BLE001
        checks["espocrm"] = {
            "ok": False,
            "configured": True,
            "reachable": False,
            "detail": f"health probe failed: {exc}"[:200],
        }

    registry = ProviderRegistry()
    usable = [str(p) for p in registry.usable_providers()]
    checks["llm_providers"] = {
        "ok": bool(usable),
        "configured": settings.has_anthropic() or settings.has_openai(),
        "usable": usable,
        "detail": (
            ", ".join(usable) + " usable"
            if usable
            else "no provider key configured; model calls are unavailable"
        ),
    }

    # A dependency nobody has configured yet is not an outage — except EspoCRM,
    # once the write path exists. Phase 2 made CRM writes load-bearing, so an
    # unconfigured EspoCRM is a real readiness failure. LLM keys stay optional:
    # a local checkout without providers is still a valid state for everything
    # that is not extraction.
    unconfigured = sorted(
        name for name, check in checks.items() if not check.get("configured", True)
    )
    failing = sorted(
        name
        for name, check in checks.items()
        if check.get("configured", True) and not check.get("ok", False)
    )
    if "espocrm" in unconfigured and "espocrm" not in failing:
        failing.append("espocrm")
        failing.sort()

    if failing:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "degraded" if failing else "ok",
        "failing": failing,
        "unconfigured": unconfigured,
        "checks": checks,
    }
