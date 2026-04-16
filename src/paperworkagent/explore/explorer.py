"""Claim Explorer orchestrator: Round 1 → Round 2 → final sort."""

from __future__ import annotations

import asyncio
import logging
import time

from paperworkagent.common.cache import FileCache
from paperworkagent.common.llm import LLMClient, LLMCallError
from paperworkagent.explore.config import ExploreSettings
from paperworkagent.explore.dedup import PaperDeduplicator
from paperworkagent.explore.models import (
    ExploreInput,
    ExploreIssue,
    ExploreIssueType,
    ExploreOutput,
    ExploreStatus,
    ExploredPaper,
    PaperData,
    Relevance,
    SearchRound,
)
from paperworkagent.explore.providers.base import BaseProvider
from paperworkagent.explore.providers.core_ac import COREProvider
from paperworkagent.explore.providers.crossref import CrossrefProvider
from paperworkagent.explore.providers.europepmc import EuropePMCProvider
from paperworkagent.explore.providers.openalex import OpenAlexProvider
from paperworkagent.explore.providers.pubmed import PubMedProvider
from paperworkagent.explore.providers.semantic_scholar import SemanticScholarProvider
from paperworkagent.explore.query_generator import generate_queries
from paperworkagent.explore.relevance_filter import filter_by_relevance

logger = logging.getLogger(__name__)

_SUMMARY_SYSTEM = """\
You are an academic research assistant.
Given information about a literature search, write a concise summary in Korean (1-2 sentences).
Return a JSON object: {"summary": "..."}"""

_SUMMARY_USER = """\
Claim: "{claim_text}"
Queries used: {queries}
Papers found after dedup: {dedup_count}
Papers kept after relevance filter: {kept_count}
Top papers: {top_titles}

Summarize the search results in Korean."""


def _build_providers(settings: ExploreSettings) -> list[BaseProvider]:
    builders: dict[str, BaseProvider] = {
        "openalex": OpenAlexProvider(email=settings.providers.openalex_email),
        "europepmc": EuropePMCProvider(),
        "crossref": CrossrefProvider(polite_email=settings.providers.openalex_email),
        "semantic_scholar": SemanticScholarProvider(
            api_key=settings.providers.semantic_scholar_api_key,
        ),
        "pubmed": PubMedProvider(api_key=settings.providers.pubmed_api_key),
        "core": COREProvider(api_key=settings.providers.core_api_key),
    }
    return [builders[name] for name in settings.providers.enabled if name in builders]


async def explore(inp: ExploreInput, settings: ExploreSettings) -> ExploreOutput:
    """Run the full exploration pipeline for a single claim."""
    issues: list[ExploreIssue] = []
    search_log: list[SearchRound] = []

    cache = FileCache(settings.cache.directory, enabled=settings.cache.enabled)
    llm = LLMClient(
        api_key=settings.llm.api_key,
        default_model=settings.llm.model,
        max_calls=settings.max_llm_calls,
        timeout=settings.llm.query_generation.timeout_seconds,
    )
    providers = _build_providers(settings)
    semaphore = asyncio.Semaphore(settings.providers.semaphore_limit)

    try:
        # ── Round 1: multi-angle search ──────────────────────────────────
        logger.info("")
        logger.info("━━━ Round 1: 다중 각도 초기 검색 ━━━")
        r1_start = time.monotonic()

        logger.info("  LLM에 검색 질의 생성 요청 중...")
        queries = await generate_queries(
            inp.claim_text,
            inp.claim_context,
            llm,
            cache,
            model=settings.llm.query_generation.model,
        )

        if not queries:
            issues.append(ExploreIssue(
                round=1,
                type=ExploreIssueType.LLM_FAILURE,
                message="검색 질의 생성에 실패했습니다",
            ))
            return _make_output(ExploreStatus.FAILED, issues, [], search_log,
                                "검색 질의 생성 실패로 탐색을 수행하지 못했습니다.")

        for i, q in enumerate(queries, 1):
            logger.info("  질의 %d: %s", i, q)

        logger.info("  %d개 질의 × %d개 provider 검색 시작...",
                     len(queries), len(providers))
        deduplicator = PaperDeduplicator()
        provider_failures: list[str] = []

        async def _search_one(provider: BaseProvider, query: str) -> list[PaperData]:
            async with semaphore:
                cache_cat = f"provider/{provider.name}"
                cache_key = (provider.name, query)
                cached = cache.get(cache_cat, cache_key)
                if cached is not None:
                    return [PaperData(**p) for p in cached]
                try:
                    results = await provider.search(query, settings.providers.max_results_per_query)
                except Exception as exc:
                    logger.warning("%s search error for %r: %s", provider.name, query, exc)
                    provider_failures.append(provider.name)
                    return []
                cache.put(
                    cache_cat,
                    cache_key,
                    input_data={"provider": provider.name, "query": query},
                    output_data=[p.model_dump() for p in results],
                )
                return results

        tasks = [
            _search_one(provider, query)
            for query in queries
            for provider in providers
        ]
        all_results = await asyncio.gather(*tasks)

        for batch in all_results:
            for paper in batch:
                deduplicator.add_or_merge(paper)

        deduped_papers = deduplicator.papers
        r1_duration = time.monotonic() - r1_start

        raw_total = sum(len(batch) for batch in all_results)
        logger.info("  검색 완료: 원시 %d편 → 중복 제거 후 %d편 (%.1f초)",
                     raw_total, len(deduped_papers), r1_duration)

        if provider_failures:
            unique_failures = sorted(set(provider_failures))
            issues.append(ExploreIssue(
                round=1,
                type=ExploreIssueType.PROVIDER_FAILURE,
                message=f"일부 provider 검색에 실패했습니다: {', '.join(unique_failures)}",
                detail=", ".join(unique_failures),
            ))

        search_log.append(SearchRound(
            round=1,
            type="initial_search",
            queries=queries,
            papers_found=len(deduped_papers),
            papers_kept=len(deduped_papers),
            duration_seconds=round(r1_duration, 2),
        ))

        if not deduped_papers:
            issues.append(ExploreIssue(
                round=1,
                type=ExploreIssueType.NO_RESULTS,
                message="검색 결과가 없습니다",
            ))
            return _make_output(ExploreStatus.FAILED, issues, [], search_log,
                                "검색 결과가 없어 탐색을 완료하지 못했습니다.")

        # ── Round 2: relevance filter ────────────────────────────────────
        logger.info("")
        logger.info("━━━ Round 2: 관련성 빠른 필터 ━━━")
        total_batches = (len(deduped_papers) + settings.batch_size - 1) // settings.batch_size
        logger.info("  %d편을 %d개 batch(각 %d편)로 LLM 판단 중...",
                     len(deduped_papers), total_batches, settings.batch_size)
        r2_start = time.monotonic()

        try:
            explored_papers, failed_papers = await filter_by_relevance(
                inp.claim_text,
                deduped_papers,
                llm,
                batch_size=settings.batch_size,
                model=settings.llm.relevance_filter.model,
            )
        except LLMCallError as exc:
            issues.append(ExploreIssue(
                round=2,
                type=ExploreIssueType.LLM_FAILURE,
                message="관련성 판단 LLM 호출이 완전히 실패했습니다",
                detail=str(exc),
            ))
            r2_duration = time.monotonic() - r2_start
            search_log.append(SearchRound(
                round=2,
                type="relevance_filter",
                queries=[],
                papers_found=len(deduped_papers),
                papers_kept=0,
                duration_seconds=round(r2_duration, 2),
            ))
            return _make_output(ExploreStatus.FAILED, issues, [], search_log,
                                "관련성 판단에 실패하여 결과를 반환하지 못했습니다.")

        if failed_papers:
            issues.append(ExploreIssue(
                round=2,
                type=ExploreIssueType.LLM_PARSE_FAILURE,
                message=f"{len(failed_papers)}개 논문의 관련성 판단에 실패했습니다 (unrelated 처리)",
                detail=f"failed_count={len(failed_papers)}",
            ))

        r2_duration = time.monotonic() - r2_start

        high_count = sum(1 for p in explored_papers if p.relevance == Relevance.HIGH)
        med_count = sum(1 for p in explored_papers if p.relevance == Relevance.MEDIUM)
        low_count = sum(1 for p in explored_papers if p.relevance == Relevance.LOW)
        logger.info("  판단 완료: high=%d, medium=%d, low=%d, unrelated=%d (%.1f초)",
                     high_count, med_count, low_count,
                     len(deduped_papers) - len(explored_papers) - len(failed_papers),
                     r2_duration)

        search_log.append(SearchRound(
            round=2,
            type="relevance_filter",
            queries=[],
            papers_found=len(deduped_papers),
            papers_kept=len(explored_papers),
            duration_seconds=round(r2_duration, 2),
        ))

        # ── Final: sort and trim ─────────────────────────────────────────
        _RELEVANCE_ORDER = {Relevance.HIGH: 0, Relevance.MEDIUM: 1, Relevance.LOW: 2}
        explored_papers.sort(key=lambda p: _RELEVANCE_ORDER.get(p.relevance, 3))
        final_papers = explored_papers[: inp.max_papers]

        logger.info("")
        logger.info("━━━ 최종 정리 ━━━")
        logger.info("  관련성 순 정렬 후 상위 %d편 선정", len(final_papers))

        # ── Summary ──────────────────────────────────────────────────────
        logger.info("  요약 생성 중...")
        summary = await _generate_summary(inp.claim_text, queries, deduped_papers,
                                          final_papers, llm, settings)

        status = ExploreStatus.SUCCESS if not issues else ExploreStatus.PARTIAL
        return _make_output(status, issues, final_papers, search_log, summary)

    finally:
        for provider in providers:
            await provider.close()


async def _generate_summary(
    claim_text: str,
    queries: list[str],
    deduped: list[PaperData],
    final: list[ExploredPaper],
    llm: LLMClient,
    settings: ExploreSettings,
) -> str:
    top_titles = ", ".join(f'"{p.title}"' for p in final[:3]) or "(없음)"
    user_msg = _SUMMARY_USER.format(
        claim_text=claim_text,
        queries=queries,
        dedup_count=len(deduped),
        kept_count=len(final),
        top_titles=top_titles,
    )
    try:
        result = await llm.complete_json(
            system=_SUMMARY_SYSTEM,
            user=user_msg,
            model=settings.llm.summary.model,
        )
        return result.get("summary", "") if isinstance(result, dict) else ""
    except Exception as exc:
        logger.warning("Summary generation failed: %s", exc)
        return f"총 {len(final)}편의 관련 문헌을 확인함."


def _make_output(
    status: ExploreStatus,
    issues: list[ExploreIssue],
    papers: list[ExploredPaper],
    search_log: list[SearchRound],
    summary: str,
) -> ExploreOutput:
    return ExploreOutput(
        status=status,
        issues=issues,
        papers=papers,
        search_log=search_log,
        summary=summary,
    )
