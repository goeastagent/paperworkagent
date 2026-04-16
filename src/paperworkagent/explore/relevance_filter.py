"""Round 2: Batch relevance filtering via LLM."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from paperworkagent.explore.dedup import get_paper_identifier
from paperworkagent.common.llm import LLMClient, LLMCallError, LLMParseError
from paperworkagent.explore.models import (
    ExploredPaper,
    PaperData,
    Relevance,
    DiscoveryMethod,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an academic citation advisor.
A researcher needs to find citable references for a specific claim in their paper.
Given the claim and a batch of candidate papers (title, year, abstract),
judge whether each candidate is appropriate to cite as a reference for this claim.

Judgment criteria — think "would a reviewer expect this paper to be cited here?":
- high: Essential reference. Original paper, seminal work, or authoritative source that
  directly supports, defines, or validates what the claim states. Must be cited.
- medium: Useful reference. Provides indirect support, related methodology comparison,
  or relevant background. Could strengthen the claim if cited.
- low: Marginal. Same broad field but not something a reviewer would expect cited for
  this specific claim.
- unrelated: Not citable for this claim. Merely uses the same tool/method in an
  unrelated domain, or has no meaningful connection.

For each paper, return:
- id: the sequential number of the paper in the list
- relevance: one of "high", "medium", "low", "unrelated"
- reason: one sentence in Korean explaining why

Return a JSON object: {"judgments": [{"id": 1, "relevance": "high", "reason": "..."}, ...]}
You must return a judgment for every paper in the list."""

_USER_TEMPLATE = """\
Claim: "{claim_text}"

Papers:
{papers_block}

Judge the relevance of each paper to the claim."""

MAX_RETRIES = 2


@dataclass
class _PendingPaper:
    batch_id: int
    paper: PaperData


def _build_paper_line(idx: int, paper: PaperData) -> str:
    id_info_parts: list[str] = []
    if paper.doi:
        id_info_parts.append(f"doi: {paper.doi}")
    if paper.pmid:
        id_info_parts.append(f"pmid: {paper.pmid}")
    id_info = f" [{', '.join(id_info_parts)}]" if id_info_parts else ""

    year_str = f" ({paper.year})" if paper.year else ""
    abstract_str = paper.abstract or "(no abstract)"
    return f'{idx}. "{paper.title}"{year_str}{id_info} - Abstract: {abstract_str}'


async def filter_by_relevance(
    claim_text: str,
    papers: list[PaperData],
    llm: LLMClient,
    batch_size: int = 10,
    model: str | None = None,
) -> tuple[list[ExploredPaper], list[PaperData]]:
    """Judge relevance for all papers in batches.

    Returns:
        A tuple of (explored papers with relevance, papers that failed all retries).
    """
    explored: list[ExploredPaper] = []
    all_failed: list[PaperData] = []

    pending = [_PendingPaper(batch_id=i + 1, paper=p) for i, p in enumerate(papers)]

    total_batches = (len(pending) + batch_size - 1) // batch_size
    for batch_idx, batch_start in enumerate(range(0, len(pending), batch_size), 1):
        batch = pending[batch_start : batch_start + batch_size]
        logger.info("    batch %d/%d (%d편 판단 중...)", batch_idx, total_batches, len(batch))
        batch_explored, batch_failed = await _process_batch_with_retries(
            claim_text, batch, llm, model
        )
        explored.extend(batch_explored)
        all_failed.extend(batch_failed)

    return explored, all_failed


async def _process_batch_with_retries(
    claim_text: str,
    batch: list[_PendingPaper],
    llm: LLMClient,
    model: str | None,
) -> tuple[list[ExploredPaper], list[PaperData]]:
    """Process a single batch, retrying failed items up to MAX_RETRIES times."""
    remaining = list(batch)
    explored: list[ExploredPaper] = []

    for attempt in range(1 + MAX_RETRIES):
        if not remaining:
            break

        papers_block = "\n".join(
            _build_paper_line(p.batch_id, p.paper) for p in remaining
        )
        user_msg = _USER_TEMPLATE.format(claim_text=claim_text, papers_block=papers_block)

        try:
            result = await llm.complete_json(system=_SYSTEM_PROMPT, user=user_msg, model=model)
        except LLMCallError as exc:
            logger.error("LLM call failed on attempt %d: %s", attempt + 1, exc)
            break
        except LLMParseError as exc:
            logger.warning("LLM parse failed on attempt %d: %s", attempt + 1, exc)
            if attempt < MAX_RETRIES:
                continue
            break

        judgments: list[dict] = []
        if isinstance(result, dict):
            judgments = result.get("judgments", [])
        elif isinstance(result, list):
            judgments = result

        judged_ids: set[int] = set()
        for j in judgments:
            try:
                j_id = int(j["id"])
                relevance_str = j["relevance"]
                reason = j.get("reason", "")
                relevance = Relevance(relevance_str)
            except (KeyError, ValueError, TypeError):
                continue

            matching = [p for p in remaining if p.batch_id == j_id]
            if not matching:
                continue
            pp = matching[0]
            judged_ids.add(j_id)

            if relevance == Relevance.UNRELATED:
                continue

            explored.append(
                ExploredPaper(
                    doi=pp.paper.doi,
                    pmid=pp.paper.pmid,
                    pmcid=pp.paper.pmcid,
                    title=pp.paper.title,
                    authors=pp.paper.authors,
                    year=pp.paper.year,
                    abstract=pp.paper.abstract,
                    venue=pp.paper.venue,
                    relevance=relevance,
                    relevance_reason=reason,
                    discovery_method=DiscoveryMethod.INITIAL_SEARCH,
                    discovered_via=None,
                )
            )

        remaining = [p for p in remaining if p.batch_id not in judged_ids]

        if not remaining:
            break
        if attempt < MAX_RETRIES:
            logger.info(
                "Retrying %d unjudged papers (attempt %d/%d)",
                len(remaining),
                attempt + 2,
                1 + MAX_RETRIES,
            )

    failed_papers = [p.paper for p in remaining]
    return explored, failed_papers
