from __future__ import annotations

import httpx

from paperworkagent.infra.cache import Cache
from paperworkagent.retrieve.providers.base import PaperResult


async def fetch_fulltext(paper: PaperResult, cache: Cache | None = None) -> str | None:
    """Attempt to fetch full-text for a paper via OA routes.

    Priority: Europe PMC XML -> PMC OA -> Unpaywall URL -> None (abstract fallback).
    """
    if paper.pmcid:
        text = await _fetch_europepmc_fulltext(paper.pmcid, cache)
        if text:
            return text

    if paper.open_access_url:
        text = await _fetch_url_text(paper.open_access_url, cache)
        if text:
            return text

    return None


async def _fetch_europepmc_fulltext(pmcid: str, cache: Cache | None) -> str | None:
    import re

    cache_params = {"pmcid": pmcid, "type": "fulltext"}
    if cache:
        cached = cache.get("fulltext", cache_params)
        if cached is not None:
            return cached

    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        raw = resp.text

    plain = re.sub(r"<[^>]+>", " ", raw)
    plain = re.sub(r"\s+", " ", plain).strip()

    if cache and plain:
        cache.set("fulltext", cache_params, plain, ttl_days=30)
    return plain or None


async def _fetch_url_text(url: str, cache: Cache | None) -> str | None:
    import re

    cache_params = {"url": url, "type": "fulltext"}
    if cache:
        cached = cache.get("fulltext", cache_params)
        if cached is not None:
            return cached

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
            content_type = resp.headers.get("content-type", "")
            if "html" in content_type or "xml" in content_type:
                plain = re.sub(r"<[^>]+>", " ", resp.text)
                plain = re.sub(r"\s+", " ", plain).strip()
                if cache and plain:
                    cache.set("fulltext", cache_params, plain, ttl_days=30)
                return plain or None
            elif "pdf" in content_type:
                return None
    except Exception:
        return None
    return None
