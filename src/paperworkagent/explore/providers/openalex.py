from __future__ import annotations

import logging
from typing import Any

import httpx

from paperworkagent.explore.models import PaperData
from paperworkagent.explore.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.openalex.org"


def _parse_paper(work: dict[str, Any]) -> PaperData | None:
    """Convert an OpenAlex work object to PaperData."""
    title = work.get("title")
    if not title:
        return None

    doi_raw: str | None = work.get("doi")
    doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None

    ids = work.get("ids") or {}
    pmid_raw: str | None = ids.get("pmid")
    pmid = pmid_raw.replace("https://pubmed.ncbi.nlm.nih.gov/", "") if pmid_raw else None
    pmcid_raw: str | None = ids.get("pmcid")
    pmcid = pmcid_raw.replace("https://www.ncbi.nlm.nih.gov/pmc/articles/", "").rstrip("/") if pmcid_raw else None

    authorships = work.get("authorships") or []
    authors = []
    for a in authorships:
        author_obj = a.get("author") or {}
        name = author_obj.get("display_name")
        if name:
            authors.append(name)

    year = work.get("publication_year")

    abstract_index: dict[str, list[int]] | None = work.get("abstract_inverted_index")
    abstract: str | None = None
    if abstract_index:
        try:
            token_positions: list[tuple[str, int]] = []
            for token, positions in abstract_index.items():
                for pos in positions:
                    token_positions.append((token, pos))
            token_positions.sort(key=lambda x: x[1])
            abstract = " ".join(t for t, _ in token_positions)
        except Exception:
            abstract = None

    venue: str | None = None
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    venue = source.get("display_name")

    return PaperData(
        doi=doi,
        pmid=pmid,
        pmcid=pmcid,
        title=title,
        authors=authors,
        year=year,
        abstract=abstract,
        venue=venue,
        source_provider="openalex",
    )


class OpenAlexProvider(BaseProvider):
    name = "openalex"

    def __init__(self, email: str = "") -> None:
        headers: dict[str, str] = {}
        if email:
            headers["User-Agent"] = f"mailto:{email}"
        self._client = httpx.AsyncClient(base_url=_BASE_URL, headers=headers, timeout=15)

    async def search(self, query: str, max_results: int = 20) -> list[PaperData]:
        params: dict[str, Any] = {
            "search": query,
            "per_page": min(max_results, 50),
            "select": "id,doi,ids,title,authorships,publication_year,abstract_inverted_index,primary_location",
        }
        try:
            resp = await self._client.get("/works", params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("OpenAlex search failed for %r: %s", query, exc)
            return []

        results: list[dict[str, Any]] = resp.json().get("results") or []
        papers: list[PaperData] = []
        for work in results:
            paper = _parse_paper(work)
            if paper:
                papers.append(paper)
        return papers

    async def close(self) -> None:
        await self._client.aclose()
