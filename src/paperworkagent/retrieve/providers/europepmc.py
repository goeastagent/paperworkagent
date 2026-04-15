from __future__ import annotations

import httpx

from paperworkagent.infra.cache import Cache
from paperworkagent.retrieve.providers.base import BaseProvider, PaperResult, SearchQuery

_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"


class EuropePMCProvider(BaseProvider):
    name = "europepmc"

    def __init__(self, cache: Cache | None = None):
        self._cache = cache

    def _parse_result(self, r: dict) -> PaperResult:
        authors = []
        author_str = r.get("authorString", "")
        if author_str:
            authors = [a.strip() for a in author_str.split(",")][:10]

        year_str = r.get("pubYear")
        year = int(year_str) if year_str and year_str.isdigit() else None

        doi = r.get("doi")
        pmid = r.get("pmid")
        pmcid = r.get("pmcid")

        is_oa = r.get("isOpenAccess") == "Y"
        oa_url = None
        if pmcid and is_oa:
            oa_url = f"https://europepmc.org/articles/{pmcid}"

        return PaperResult(
            paper_id=doi or pmid or pmcid or r.get("id", ""),
            title=r.get("title", ""),
            authors=authors,
            year=year,
            venue=r.get("journalTitle"),
            abstract=r.get("abstractText") or None,
            doi=doi,
            pmid=pmid,
            pmcid=pmcid,
            source_provider=self.name,
            open_access_url=oa_url,
            cited_by_count=r.get("citedByCount"),
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

        params = {
            "query": search_term,
            "format": "json",
            "pageSize": min(query.max_results, 50),
            "sort": "RELEVANCE",
            "resultType": "core",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        results_list = data.get("resultList", {}).get("result", [])
        results = [self._parse_result(r) for r in results_list]

        if self._cache:
            self._cache.set("search", cache_params, results, ttl_days=7)
        return results

    async def get_references(self, paper_id: str) -> list[str]:
        source = "MED"
        url = f"{_FULLTEXT_URL}/{source}/{paper_id}/references?format=json&page=1&pageSize=50"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
        refs = data.get("referenceList", {}).get("reference", [])
        return [r.get("doi", "") for r in refs if r.get("doi")]

    async def get_cited_by(self, paper_id: str) -> list[str]:
        source = "MED"
        url = f"{_FULLTEXT_URL}/{source}/{paper_id}/citations?format=json&page=1&pageSize=50"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
        cits = data.get("citationList", {}).get("citation", [])
        return [c.get("doi", "") for c in cits if c.get("doi")]

    async def get_fulltext(self, pmcid: str) -> str | None:
        """Fetch full-text XML from Europe PMC, return plain text or None."""
        cache_params = {"provider": self.name, "pmcid": pmcid, "type": "fulltext"}
        if self._cache:
            cached = self._cache.get("fulltext", cache_params)
            if cached is not None:
                return cached

        url = f"{_FULLTEXT_URL}/{pmcid}/fullTextXML"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            text = resp.text

        import re
        plain = re.sub(r"<[^>]+>", " ", text)
        plain = re.sub(r"\s+", " ", plain).strip()

        if self._cache and plain:
            self._cache.set("fulltext", cache_params, plain, ttl_days=30)
        return plain or None
