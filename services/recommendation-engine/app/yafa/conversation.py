"""Conversation memory, separate from page context (spec Phase 2 §38).

In-process TTL store keyed by conversation_id. It persists extracted slots and
the last page context so "What about this one?" resolves against the NEW page
product while wedding/look context survives navigation.

Single-process by design for this phase: the browser always reaches Yafa
through the Go backend, which owns durable session state; this cache only
smooths multi-turn orchestration inside one service instance.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.yafa.schemas import PageContext

_TTL_SECONDS = 60 * 60  # one hour of inactivity
_MAX_TURNS = 40


@dataclass
class Conversation:
    conversation_id: str
    user_id: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turns: list[dict[str, str]] = field(default_factory=list)
    slots: dict[str, Any] = field(default_factory=dict)
    page_context: PageContext | None = None
    # Kind of the most recent image attachment ("outfit"/"selfie"/"reference").
    last_attachment_kind: str | None = None
    # Colours derived from the most recent outfit image (uncertainty included).
    last_attachment_colours: list[str] = field(default_factory=list)
    last_attachment_runner_up: str | None = None

    def record_attachment(self, kind: str, colours: list[str], runner_up: str | None) -> None:
        self.last_attachment_kind = kind
        self.last_attachment_colours = list(colours)[:4]
        self.last_attachment_runner_up = runner_up
        self.updated_at = time.time()

    def record_turn(self, role: str, content: str) -> None:
        self.turns.append({"role": role, "content": content[:500]})
        if len(self.turns) > _MAX_TURNS:
            del self.turns[: len(self.turns) - _MAX_TURNS]
        self.updated_at = time.time()

    def absorb_slots(self, new_slots: dict[str, Any]) -> None:
        """First extraction wins per slot; explicit later repeats may update."""
        for key, value in new_slots.items():
            self.slots.setdefault(key, value)
        self.updated_at = time.time()


class ConversationStore:
    def __init__(self, ttl_seconds: int = _TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._conversations: dict[str, Conversation] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        conversation_id: str | None,
        user_id: str | None = None,
        page_context: PageContext | None = None,
    ) -> Conversation:
        with self._lock:
            self._evict_expired()
            if conversation_id:
                existing = self._conversations.get(conversation_id)
                if existing is not None:
                    if page_context is not None:
                        existing.page_context = page_context
                    if user_id:
                        existing.user_id = user_id
                    return existing
            fresh = Conversation(
                conversation_id=conversation_id or f"conv_{uuid.uuid4().hex}",
                user_id=user_id,
                page_context=page_context,
            )
            self._conversations[fresh.conversation_id] = fresh
            return fresh

    def _evict_expired(self) -> None:
        cutoff = time.time() - self._ttl
        expired = [
            key
            for key, conv in self._conversations.items()
            if conv.updated_at < cutoff
        ]
        for key in expired:
            del self._conversations[key]


_store: ConversationStore | None = None


def conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
