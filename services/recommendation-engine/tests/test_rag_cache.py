from __future__ import annotations

import asyncio

import pytest

from app.rag.cache import AsyncTTLCache

pytestmark = pytest.mark.asyncio


async def test_cache_coalesces_identical_concurrent_loads():
    cache = AsyncTTLCache(ttl_seconds=30, max_entries=10)
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return {"facts": ["verified"]}

    first, second = await asyncio.gather(
        cache.get_or_load("same-query", loader),
        cache.get_or_load("same-query", loader),
    )
    assert calls == 1
    assert first == second == {"facts": ["verified"]}


async def test_cache_returns_a_copy_not_mutable_shared_state():
    cache = AsyncTTLCache(ttl_seconds=30, max_entries=10)

    first = await cache.get_or_load("key", lambda: _value())
    first["facts"].append("tampered")
    second = await cache.get_or_load("key", lambda: _value())

    assert second == {"facts": ["verified"]}


async def _value():
    return {"facts": ["verified"]}
