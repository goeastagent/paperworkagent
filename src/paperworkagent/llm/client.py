from __future__ import annotations

import hashlib
import json
import logging

from paperworkagent.config import LLMSettings
from paperworkagent.infra.cache import Cache

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper around litellm with caching and retry."""

    def __init__(self, settings: LLMSettings, cache: Cache | None = None):
        self._settings = settings
        self._cache = cache

    async def complete(
        self,
        prompt: str,
        system: str = "",
        temperature: float | None = None,
    ) -> str:
        cache_key = {
            "model": self._settings.model,
            "prompt_hash": hashlib.sha256(f"{system}|{prompt}".encode()).hexdigest(),
        }
        if self._cache:
            cached = self._cache.get("llm", cache_key)
            if cached is not None:
                return cached

        import litellm

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await litellm.acompletion(
            model=f"{self._settings.provider}/{self._settings.model}",
            messages=messages,
            temperature=temperature or self._settings.temperature,
            timeout=self._settings.timeout_seconds,
            api_key=self._settings.api_key,
            num_retries=self._settings.max_retries,
        )

        content = response.choices[0].message.content
        if self._cache and content:
            self._cache.set("llm", cache_key, content, ttl_days=365)
        return content

    async def complete_json(
        self,
        prompt: str,
        system: str = "",
    ) -> dict | list | None:
        """Complete and parse as JSON. Returns None on any failure."""
        try:
            text = await self.complete(prompt, system)
        except Exception as e:
            logger.warning("LLM call failed: %s", e)
            return None

        try:
            cleaned = text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("LLM JSON parse failed: %s", e)
            return None
