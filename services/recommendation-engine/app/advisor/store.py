from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import UUID

from .models import AdvisorSession


class SessionNotFound(KeyError):
    pass


class InMemorySessionStore:
    """Thread-safe V1 store. Swap for Postgres/Redis without changing API handlers."""

    def __init__(self, ttl_hours: int = 24) -> None:
        self._items: dict[UUID, AdvisorSession] = {}
        self._lock = RLock()
        self._ttl = timedelta(hours=ttl_hours)

    def create(self, session: AdvisorSession) -> AdvisorSession:
        with self._lock:
            self._items[session.id] = session
            return session

    def get(self, session_id: UUID) -> AdvisorSession:
        self._cleanup()
        with self._lock:
            try:
                return self._items[session_id]
            except KeyError as exc:
                raise SessionNotFound(str(session_id)) from exc

    def save(self, session: AdvisorSession) -> AdvisorSession:
        session.updated_at = datetime.now(timezone.utc)
        with self._lock:
            self._items[session.id] = session
        return session

    def _cleanup(self) -> None:
        cutoff = datetime.now(timezone.utc) - self._ttl
        with self._lock:
            stale = [key for key, value in self._items.items() if value.updated_at < cutoff]
            for key in stale:
                del self._items[key]
