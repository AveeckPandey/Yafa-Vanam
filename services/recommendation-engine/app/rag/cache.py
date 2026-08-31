"""Bounded, request-coalescing cache for safe RAG retrieval results.

This cache intentionally stores only public, verified retrieval results. It
has no user data, is bounded in memory, and uses a deployment/corpus namespace
so a release can invalidate every local cache without a restart. A shared
Redis cache can replace this implementation when multiple replicas need a
cross-instance cache; the contract stays the same.
"""

from __future__ import annotations

import asyncio
import copy
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


class AsyncTTLCache:
    """Small in-process TTL/LRU cache with single-flight request coalescing."""

    def __init__(self, *, ttl_seconds: int, max_entries: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._items: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._inflight: dict[str, asyncio.Task[T]] = {}
        self._lock = asyncio.Lock()

    async def get_or_load(self, key: str, loader: Callable[[], Awaitable[T]]) -> T:
        if self._ttl_seconds <= 0:
            return await loader()

        async with self._lock:
            self._evict_expired_locked()
            hit = self._items.get(key)
            if hit is not None:
                self._items.move_to_end(key)
                return copy.deepcopy(hit[1])
            task = self._inflight.get(key)
            if task is None:
                task = asyncio.create_task(loader())
                self._inflight[key] = task

        try:
            value = await task
        except Exception:
            raise
        else:
            async with self._lock:
                self._items[key] = (time.monotonic() + self._ttl_seconds, copy.deepcopy(value))
                self._items.move_to_end(key)
                while len(self._items) > self._max_entries:
                    self._items.popitem(last=False)
            return copy.deepcopy(value)
        finally:
            async with self._lock:
                self._inflight.pop(key, None)

    async def get(self, key: str) -> T | None:
        """Return a still-valid cached value without invoking a loader."""
        if self._ttl_seconds <= 0:
            return None
        async with self._lock:
            self._evict_expired_locked()
            hit = self._items.get(key)
            if hit is None:
                return None
            self._items.move_to_end(key)
            return copy.deepcopy(hit[1])

    async def invalidate_all(self) -> None:
        """Drop results after a corpus revision, revocation, or permission change."""
        async with self._lock:
            self._items.clear()

    def _evict_expired_locked(self) -> None:
        now = time.monotonic()
        for key in [key for key, (expires_at, _) in self._items.items() if expires_at <= now]:
            self._items.pop(key, None)
