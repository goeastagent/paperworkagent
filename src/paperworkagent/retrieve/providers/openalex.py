from __future__ import annotations

import httpx

from paperworkagent.infra.cache import Cache
from paperworkagent.retrieve.providers.base import BaseProvider, PaperResult, SearchQuery

_BASE_URL = "https://api.openalex.org"


class OpenAlexProvider(BaseProvider):
    name = "openalex"

    def __init__(self, email: str = "", cache: Cache | None = None):
        self._email = email
        self._cache = cache

    def _params(self, extra: dict | None = None) -> dict:
        p: dict = {}
        if self._email:
            p["mailto"] = self._email
        if extra:
            p.update(extra)
        return p

    def _parse_work(self, work: dict) -> PaperResult:
        authorship = work.get("authorships", [])
        authors = []
        for a in authorship[:10]:
            author = a.get("author", {})
            name = author.get("display_name", "")
            if name:
                authors.append(name)

        ids = work.get("ids", {})
        doi_raw = ids.get("doi") or work.get("doi") or ""
        doi = doi_raw.replace("https://doi.org/", "") if doi_raw else None
        pmid_raw = ids.get("pmid") or ""
        pmid = pmid_raw.replace("https://pubmed.ncbi.nlm.nih.gov/", "").strip("/") or None
        pmcid = ids.get("pmcid") or None

        oa = work.get("open_access", {})
        oa_url = oa.get("oa_url")

        abstract = work.get("abstract") or None
        if not abstract:
            inv = work.get("abstract_inverted_index")
            if inv:
                abstract = _reconstruct_abstract(inv)

        return PaperResult(
            paper_id=doi or work.get("id", ""),
            title=work.get("title", "") or "",
            authors=authors,
            year=work.get("publication_year"),
            venue=(work.get("primary_location") or {}).get("source", {}).get("display_name"),
            abstract=abstract,
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            source_provider=self.name,
            open_access_url=oa_url,
            cited_by_count=work.get("cited_by_count"),
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

        params = self._params({
            "search": search_term,
            "per_page": min(query.max_results, 50),
            "sort": "relevance_score:desc",
        })
        if query.year_range:
            params["filter"] = f"publication_year:{query.year_range[0]}-{query.year_range[1]}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{_BASE_URL}/works", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = [self._parse_work(w) for w in data.get("results", [])]

        if self._cache:
            self._cache.set("search", cache_params, results, ttl_days=7)
        return results

    async def get_references(self, paper_id: str) -> list[str]:
        url = f"{_BASE_URL}/works"
        params = self._params({"filter": f"cites:{paper_id}", "per_page": 50})
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
        return [w.get("doi", w.get("id", "")) for w in data.get("results", [])]

    async def get_cited_by(self, paper_id: str) -> list[str]:
        url = f"{_BASE_URL}/works"
        params = self._params({"filter": f"cited_by:{paper_id}", "per_page": 50})
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return []
            data = resp.json()
        return [w.get("doi", w.get("id", "")) for w in data.get("results", [])]


def _reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract text from OpenAlex's inverted index format."""
    positions: list[tuple[int, str]] = []
    for word, indices in inverted_index.items():
        for idx in indices:
            positions.append((idx, word))
    positions.sort()
    return " ".join(word for _, word in positions)
