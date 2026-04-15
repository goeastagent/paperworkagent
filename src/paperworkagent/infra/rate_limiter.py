from __future__ import annotations

import asyncio
import random


class RateLimiter:
    """Per-provider semaphore with exponential backoff retry."""

    def __init__(self, max_concurrent: int = 5, max_retries: int = 3):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_retries = max_retries

    async def execute(self, coro_factory, *args, **kwargs):
        """Execute an async callable with semaphore gating and retry."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            async with self._semaphore:
                try:
                    return await coro_factory(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < self._max_retries:
                        wait = min(2**attempt + random.random(), 16)
                        await asyncio.sleep(wait)
        raise last_exc  # type: ignore[misc]


class RateLimiterPool:
    """A collection of per-provider rate limiters."""

    _DEFAULT_LIMITS: dict[str, int] = {
        "openalex": 5,
        "crossref": 3,
        "europepmc": 3,
        "semanticscholar": 1,
    }

    def __init__(self, overrides: dict[str, int] | None = None):
        limits = {**self._DEFAULT_LIMITS, **(overrides or {})}
        self._limiters: dict[str, RateLimiter] = {
            name: RateLimiter(max_concurrent=n) for name, n in limits.items()
        }

    def get(self, provider: str) -> RateLimiter:
        if provider not in self._limiters:
            self._limiters[provider] = RateLimiter(max_concurrent=3)
        return self._limiters[provider]
