from __future__ import annotations

import httpx

from paperworkagent.infra.cache import Cache
from paperworkagent.retrieve.providers.base import BaseProvider, PaperResult, SearchQuery

_BASE_URL = "https://api.crossref.org"


class CrossrefProvider(BaseProvider):
    name = "crossref"

    def __init__(self, email: str = "", cache: Cache | None = None):
        self._email = email
        self._cache = cache

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._email:
            h["User-Agent"] = f"PaperworkAgent/0.1 (mailto:{self._email})"
        return h

    def _parse_item(self, item: dict) -> PaperResult:
        title_parts = item.get("title", [])
        title = title_parts[0] if title_parts else ""

        authors = []
        for a in item.get("author", [])[:10]:
            name = f"{a.get('given', '')} {a.get('family', '')}".strip()
            if name:
                authors.append(name)

        year = None
        date_parts = (item.get("published") or item.get("issued") or {}).get("date-parts", [[]])
        if date_parts and date_parts[0]:
            year = date_parts[0][0]

        doi = item.get("DOI")
        abstract = item.get("abstract", "")
        if abstract:
            import re
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        venue_list = item.get("container-title", [])
        venue = venue_list[0] if venue_list else None

        return PaperResult(
            paper_id=doi or "",
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            abstract=abstract or None,
            doi=doi,
            source_provider=self.name,
        )

    async def search(self, query: SearchQuery) -> list[PaperResult]:
        cache_params = {"provider": self.name, "keywords": query.keywords}
        if self._cache:
            cached = self._cache.get("search", cache_params)
            if cached is not None:
                return cached

        search_term = " ".join(query.keywords)
        if not search_term.strip():
            return []

        params: dict = {
            "query": search_term,
            "rows": min(query.max_results, 50),
            "sort": "relevance",
        }

        async with httpx.AsyncClient(timeout=30, headers=self._headers()) as client:
            resp = await client.get(f"{_BASE_URL}/works", params=params)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("message", {}).get("items", [])
        results = [self._parse_item(item) for item in items]

        if self._cache:
            self._cache.set("search", cache_params, results, ttl_days=7)
        return results

    async def get_references(self, paper_id: str) -> list[str]:
        url = f"{_BASE_URL}/works/{paper_id}"
        async with httpx.AsyncClient(timeout=30, headers=self._headers()) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
        refs = data.get("message", {}).get("reference", [])
        return [r.get("DOI", "") for r in refs if r.get("DOI")]

    async def get_cited_by(self, paper_id: str) -> list[str]:
        return []
