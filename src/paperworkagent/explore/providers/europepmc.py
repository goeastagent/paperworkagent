from __future__ import annotations

import logging
from typing import Any

import httpx

from paperworkagent.explore.models import PaperData
from paperworkagent.explore.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"


def _parse_paper(result: dict[str, Any]) -> PaperData | None:
    title = result.get("title")
    if not title:
        return None

    doi = result.get("doi") or None
    pmid = result.get("pmid") or None
    pmcid = result.get("pmcid") or None

    author_string: str = result.get("authorString") or ""
    authors = [a.strip() for a in author_string.split(",") if a.strip()] if author_string else []

    year_str = result.get("pubYear")
    year: int | None = None
    if year_str:
        try:
            year = int(year_str)
        except (ValueError, TypeError):
            pass

    abstract = result.get("abstractText") or None
    venue = result.get("journalTitle") or None

    return PaperData(
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        venue=venue,
        source_provider="europepmc",
    )


class EuropePMCProvider(BaseProvider):
    name = "europepmc"

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=_BASE_URL, timeout=15)

    async def search(self, query: str, max_results: int = 20) -> list[PaperData]:
        params: dict[str, Any] = {
            "query": query,
            "format": "json",
            "pageSize": min(max_results, 25),
            "resultType": "core",
        }
        try:
            resp = await self._client.get("/search", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Europe PMC search failed for %r: %s", query, exc)
            return []

        data = resp.json()
        result_list: list[dict[str, Any]] = data.get("resultList", {}).get("result") or []
        papers: list[PaperData] = []
        for item in result_list:
            paper = _parse_paper(item)
            if paper:
                papers.append(paper)
        return papers

    async def close(self) -> None:
        await self._client.aclose()
