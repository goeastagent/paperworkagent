from __future__ import annotations

import json
import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

litellm.drop_params = True


class LLMClient:
    """Thin wrapper around litellm with JSON parsing and retry."""

    def __init__(
        self,
        *,
        api_key: str,
        default_model: str,
        max_calls: int,
        timeout: int,
    ) -> None:
        self._api_key = api_key
        self._default_model = default_model
        self._max_calls = max_calls
        self._timeout = timeout
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float | None = None,
    ) -> Any:
        """Call LLM and parse the response as JSON.

        Raises ``LLMParseError`` when the response is not valid JSON.
        Raises ``LLMCallError`` on API-level failures.
        """
        effective_model = model or self._default_model
        effective_temp = temperature if temperature is not None else 0.1

        if self._call_count >= self._max_calls:
            raise LLMCallError(f"LLM call limit reached ({self._max_calls})")

        try:
            self._call_count += 1
            response = await litellm.acompletion(
                model=effective_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=effective_temp,
                response_format={"type": "json_object"},
                api_key=self._api_key,
                timeout=self._timeout,
            )
        except Exception as exc:
            raise LLMCallError(f"LLM API call failed: {exc}") from exc

        content: str = response.choices[0].message.content or ""
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMParseError(f"LLM returned invalid JSON: {content[:200]}") from exc


class LLMCallError(Exception):
    """Raised when the LLM API call itself fails."""


class LLMParseError(Exception):
    """Raised when the LLM response cannot be parsed as JSON."""
