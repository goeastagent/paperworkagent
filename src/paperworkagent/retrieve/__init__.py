"""Retrieve module: claim -> candidate papers via multiple providers."""

from __future__ import annotations

import asyncio

from paperworkagent.infra.cache import Cache
from paperworkagent.infra.rate_limiter import RateLimiterPool
from paperworkagent.llm.client import LLMClient
from paperworkagent.log import log
from paperworkagent.models import Claim, Paper
from paperworkagent.retrieve.deduplicator import deduplicate
from paperworkagent.retrieve.providers.base import BaseProvider, PaperResult, SearchQuery
from paperworkagent.retrieve.providers.crossref import CrossrefProvider
from paperworkagent.retrieve.providers.europepmc import EuropePMCProvider
from paperworkagent.retrieve.providers.openalex import OpenAlexProvider
from paperworkagent.retrieve.query_builder import build_query


def _create_providers(
    provider_names: list[str],
    email: str = "",
    cache: Cache | None = None,
) -> list[BaseProvider]:
    mapping: dict[str, type] = {
        "openalex": OpenAlexProvider,
        "crossref": CrossrefProvider,
        "europepmc": EuropePMCProvider,
    }
    providers = []
    for name in provider_names:
        cls = mapping.get(name)
        if cls is None:
            continue
        if name in ("openalex", "crossref"):
            providers.append(cls(email=email, cache=cache))
        else:
            providers.append(cls(cache=cache))
    return providers


def _paper_result_to_paper(pr: PaperResult) -> Paper:
    return Paper(
        paper_id=pr.paper_id,
        title=pr.title,
        authors=pr.authors,
        year=pr.year,
        venue=pr.venue,
        abstract=pr.abstract,
        doi=pr.doi,
        pmid=pr.pmid,
        pmcid=pr.pmcid,
        source_providers=pr.source_provider.split(",") if pr.source_provider else [],
        open_access_url=pr.open_access_url,
    )


async def retrieve_for_claim(
    claim: Claim,
    providers: list[BaseProvider],
    rate_limiters: RateLimiterPool,
    llm: LLMClient,
    max_results: int = 20,
) -> list[PaperResult]:
    query = await build_query(claim, llm, max_results=max_results)

    async def _search_one(provider: BaseProvider) -> list[PaperResult]:
        limiter = rate_limiters.get(provider.name)
        return await limiter.execute(provider.search, query)

    tasks = [_search_one(p) for p in providers]
    results_per_provider = await asyncio.gather(*tasks, return_exceptions=True)

    all_results: list[PaperResult] = []
    for res in results_per_provider:
        if isinstance(res, list):
            all_results.extend(res)

    return deduplicate(all_results)


async def retrieve_for_claims(
    claims: list[Claim],
    llm: LLMClient,
    provider_names: list[str] | None = None,
    email: str = "",
    cache: Cache | None = None,
    max_results_per_claim: int = 20,
) -> list[Paper]:
    if provider_names is None:
        provider_names = ["openalex", "crossref", "europepmc"]

    providers = _create_providers(provider_names, email=email, cache=cache)
    rate_limiters = RateLimiterPool()
    log.info(f"providers: {', '.join(p.name for p in providers)}")

    all_paper_results: list[PaperResult] = []
    total = len(claims)

    for i, claim in enumerate(claims):
        log.progress(i, total, f"searching for '{claim.claim_text[:50]}...'")
        results = await retrieve_for_claim(claim, providers, rate_limiters, llm, max_results_per_claim)
        all_paper_results.extend(results)

    log.progress(total, total, "search done")

    unique = deduplicate(all_paper_results)
    log.info(f"{len(all_paper_results)} raw results → {len(unique)} after dedup")
    return [_paper_result_to_paper(pr) for pr in unique]
