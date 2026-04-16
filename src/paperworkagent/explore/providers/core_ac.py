from __future__ import annotations

import logging
from typing import Any

import httpx

from paperworkagent.explore.models import PaperData
from paperworkagent.explore.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.core.ac.uk/v3"


def _parse_paper(item: dict[str, Any]) -> PaperData | None:
    title = item.get("title")
    if not title:
        return None

    doi = item.get("doi") or None

    authors_raw: list[dict[str, Any]] = item.get("authors") or []
    authors = [a.get("name", "") for a in authors_raw if a.get("name")]

    year: int | None = None
    year_published = item.get("yearPublished")
    if year_published:
        try:
            year = int(year_published)
        except (ValueError, TypeError):
            pass

    abstract = item.get("abstract") or None

    journals: list[dict[str, Any]] = item.get("journals") or []
    venue = journals[0].get("title") if journals else None

    return PaperData(
        doi=doi,
        pmid=None,
        pmcid=None,
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        venue=venue,
        source_provider="core",
    )


class COREProvider(BaseProvider):
    name = "core"

    def __init__(self, api_key: str = "") -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL, headers=headers, timeout=15
        )

    async def search(self, query: str, max_results: int = 20) -> list[PaperData]:
        params: dict[str, Any] = {
            "q": query,
            "limit": min(max_results, 100),
        }
        try:
            resp = await self._client.get("/search/works/", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("CORE search failed for %r: %s", query, exc)
            return []

        results: list[dict[str, Any]] = resp.json().get("results") or []
        papers: list[PaperData] = []
        for item in results:
            paper = _parse_paper(item)
            if paper:
                papers.append(paper)
        return papers

    async def close(self) -> None:
        await self._client.aclose()
