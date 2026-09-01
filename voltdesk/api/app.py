"""FastAPI application factory.

Owned by: Phase 1. Fully implemented.

Every route the finished system will expose is registered here now, so that
`GET /openapi.json` is a complete map of the service from Phase 1 onward and later
phases fill in bodies rather than inventing paths.
"""

from __future__ import annotations

from fastapi import FastAPI

from voltdesk import __version__
from voltdesk.api.routes import admin, documents, health, metrics, qa, review
from voltdesk.logging_setup import configure_logging, get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="VoltDesk",
        version=__version__,
        description=(
            "LLM service layer for commercial solar and battery operations. "
            "Two capabilities: document intake to CRM, and cited knowledge Q&A with "
            "explicit abstention. Routes that return 501 name the phase that implements "
            "them."
        ),
    )

    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(documents.router)
    app.include_router(qa.router)
    app.include_router(review.router)
    app.include_router(admin.router)

    logger.info("app_started", version=__version__)
    return app


app = create_app()
