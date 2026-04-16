from __future__ import annotations

from abc import ABC, abstractmethod

from paperworkagent.explore.models import PaperData


class BaseProvider(ABC):
    """Abstract base for academic search providers."""

    name: str

    @abstractmethod
    async def search(self, query: str, max_results: int = 20) -> list[PaperData]:
        """Search for papers matching *query* and return up to *max_results*."""

    async def close(self) -> None:
        """Release underlying resources (e.g. HTTP client)."""
