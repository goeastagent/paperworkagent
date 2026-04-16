from __future__ import annotations

import logging
from typing import Any

import httpx

from paperworkagent.explore.models import PaperData
from paperworkagent.explore.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.crossref.org"


def _parse_paper(item: dict[str, Any]) -> PaperData | None:
    titles: list[str] = item.get("title") or []
    title = titles[0] if titles else None
    if not title:
        return None

    doi = item.get("DOI") or None

    author_list: list[dict[str, str]] = item.get("author") or []
    authors: list[str] = []
    for a in author_list:
        family = a.get("family", "")
        given = a.get("given", "")
        name = f"{family} {given}".strip() if family else given
        if name:
            authors.append(name)

    year: int | None = None
    date_parts = (item.get("published") or item.get("created") or {}).get("date-parts")
    if date_parts and date_parts[0]:
        try:
            year = int(date_parts[0][0])
        except (ValueError, TypeError, IndexError):
            pass

    abstract = item.get("abstract") or None
    if abstract and abstract.startswith("<jats:"):
        import re
        abstract = re.sub(r"<[^>]+>", "", abstract).strip()

    venue_list: list[str] = item.get("container-title") or []
    venue = venue_list[0] if venue_list else None

    return PaperData(
        doi=doi,
        pmid=None,
        pmcid=None,
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        venue=venue,
        source_provider="crossref",
    )


class CrossrefProvider(BaseProvider):
    name = "crossref"

    def __init__(self, polite_email: str = "") -> None:
        headers: dict[str, str] = {}
        if polite_email:
            headers["User-Agent"] = f"PaperworkAgent/0.1 (mailto:{polite_email})"
        self._client = httpx.AsyncClient(base_url=_BASE_URL, headers=headers, timeout=15)

    async def search(self, query: str, max_results: int = 20) -> list[PaperData]:
        params: dict[str, Any] = {
            "query": query,
            "rows": min(max_results, 50),
            "select": "DOI,title,author,published,created,abstract,container-title",
        }
        try:
            resp = await self._client.get("/works", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Crossref search failed for %r: %s", query, exc)
            return []

        items: list[dict[str, Any]] = resp.json().get("message", {}).get("items") or []
        papers: list[PaperData] = []
        for item in items:
            paper = _parse_paper(item)
            if paper:
                papers.append(paper)
        return papers

    async def close(self) -> None:
        await self._client.aclose()
