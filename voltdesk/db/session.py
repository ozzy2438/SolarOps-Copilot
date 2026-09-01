"""Database engine and session handling.

Owned by: Phase 1. Fully implemented.

The engine is created lazily and cached. Importing this module must not connect to
anything - the package has to import on a machine with no PostgreSQL, or the unit
tests cannot run and neither can `--help`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from voltdesk.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Process-wide engine. `pool_pre_ping` because a small VM's database gets
    restarted and a stale pooled connection is an avoidable 500."""
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope. Commits on success, rolls back on any exception."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
