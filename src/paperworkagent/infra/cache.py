from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import diskcache


class Cache:
    """Thin wrapper around diskcache for provider / LLM response caching."""

    def __init__(self, directory: str | Path = ".cache", enabled: bool = True):
        self._enabled = enabled
        self._dir = Path(directory)
        self._cache: diskcache.Cache | None = None
        if enabled:
            self._dir.mkdir(parents=True, exist_ok=True)
            self._cache = diskcache.Cache(str(self._dir))

    def _make_key(self, namespace: str, params: dict[str, Any]) -> str:
        raw = json.dumps({"ns": namespace, **params}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, namespace: str, params: dict[str, Any]) -> Any | None:
        if not self._enabled or self._cache is None:
            return None
        key = self._make_key(namespace, params)
        return self._cache.get(key)

    def set(
        self, namespace: str, params: dict[str, Any], value: Any, ttl_days: int = 7
    ) -> None:
        if not self._enabled or self._cache is None:
            return
        key = self._make_key(namespace, params)
        self._cache.set(key, value, expire=ttl_days * 86400)

    def close(self) -> None:
        if self._cache is not None:
            self._cache.close()
