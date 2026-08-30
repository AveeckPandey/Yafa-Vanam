"""Small in-process conversation store for page context and chat continuity."""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from app.yafa.schemas import PageContext

_TTL_SECONDS = 60 * 60
_MAX_TURNS = 40


@dataclass
class Conversation:
    conversation_id: str
    user_id: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    turns: list[dict[str, str]] = field(default_factory=list)
    page_context: PageContext | None = None

    def record_turn(self, role: str, content: str) -> None:
        self.turns.append({"role": role, "content": content[:500]})
        if len(self.turns) > _MAX_TURNS:
            del self.turns[: len(self.turns) - _MAX_TURNS]
        self.updated_at = time.time()


class ConversationStore:
    def __init__(self, ttl_seconds: int = _TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._conversations: dict[str, Conversation] = {}
        self._lock = threading.Lock()

    def get_or_create(self, conversation_id: str | None, user_id: str | None = None, page_context: PageContext | None = None) -> Conversation:
        with self._lock:
            self._evict_expired()
            if conversation_id and (existing := self._conversations.get(conversation_id)) is not None:
                if page_context is not None:
                    existing.page_context = page_context
                if user_id:
                    existing.user_id = user_id
                return existing
            fresh = Conversation(conversation_id=conversation_id or f"conv_{uuid.uuid4().hex}", user_id=user_id, page_context=page_context)
            self._conversations[fresh.conversation_id] = fresh
            return fresh

    def _evict_expired(self) -> None:
        cutoff = time.time() - self._ttl
        for key in [key for key, conversation in self._conversations.items() if conversation.updated_at < cutoff]:
            del self._conversations[key]


_store: ConversationStore | None = None


def conversation_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store
