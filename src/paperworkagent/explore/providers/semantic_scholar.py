from __future__ import annotations

import logging
from typing import Any

import httpx

from paperworkagent.explore.models import PaperData
from paperworkagent.explore.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.semanticscholar.org/graph/v1"
_FIELDS = "paperId,externalIds,title,authors,year,abstract,venue"


def _parse_paper(item: dict[str, Any]) -> PaperData | None:
    title = item.get("title")
    if not title:
        return None

    ext_ids = item.get("externalIds") or {}
    doi = ext_ids.get("DOI")
    pmid = ext_ids.get("PubMed")
    pmcid = ext_ids.get("PubMedCentral")
    if pmcid:
        pmcid = f"PMC{pmcid}" if not pmcid.startswith("PMC") else pmcid

    authors_raw: list[dict[str, Any]] = item.get("authors") or []
    authors = [a["name"] for a in authors_raw if a.get("name")]

    return PaperData(
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        title=title,
        authors=authors,
        year=item.get("year"),
        abstract=item.get("abstract"),
        venue=item.get("venue") or None,
        source_provider="semantic_scholar",
    )


class SemanticScholarProvider(BaseProvider):
    name = "semantic_scholar"

    def __init__(self, api_key: str = "") -> None:
        headers: dict[str, str] = {}
        if api_key:
            headers["x-api-key"] = api_key
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL, headers=headers, timeout=15
        )

    async def search(self, query: str, max_results: int = 20) -> list[PaperData]:
        params: dict[str, Any] = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": _FIELDS,
        }
        try:
            resp = await self._client.get("/paper/search", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Semantic Scholar search failed for %r: %s", query, exc)
            return []

        data: list[dict[str, Any]] = resp.json().get("data") or []
        papers: list[PaperData] = []
        for item in data:
            paper = _parse_paper(item)
            if paper:
                papers.append(paper)
        return papers

    async def close(self) -> None:
        await self._client.aclose()
