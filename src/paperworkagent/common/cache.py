from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _hash_key(parts: tuple[str, ...]) -> str:
    """SHA-256 hash of concatenated parts, first 16 hex chars."""
    raw = "\n".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class FileCache:
    """File-based JSON cache organised by category subdirectories.

    Layout::

        base_dir/
        ├── provider/openalex/{hash}.json
        ├── llm/query_generation/{hash}.json
        └── llm/{hash}.json
    """

    def __init__(self, base_dir: Path, *, enabled: bool = True) -> None:
        self._base = base_dir
        self._enabled = enabled

    def get(self, category: str, key_parts: tuple[str, ...]) -> Any | None:
        if not self._enabled:
            return None
        path = self._path_for(category, key_parts)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            logger.debug("Cache hit: %s", path)
            return data["output"]
        except (json.JSONDecodeError, KeyError):
            logger.warning("Corrupt cache file, ignoring: %s", path)
            return None

    def put(self, category: str, key_parts: tuple[str, ...], *, input_data: Any, output_data: Any) -> None:
        if not self._enabled:
            return
        path = self._path_for(category, key_parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "input": input_data,
            "output": output_data,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Cache written: %s", path)

    def _path_for(self, category: str, key_parts: tuple[str, ...]) -> Path:
        h = _hash_key(key_parts)
        return self._base / category / f"{h}.json"
