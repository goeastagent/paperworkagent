"""Round 1: Generate multi-angle search queries from a claim."""

from __future__ import annotations

import logging

from paperworkagent.explore.cache import FileCache
from paperworkagent.explore.llm import LLMClient, LLMCallError, LLMParseError
from paperworkagent.explore.models import ClaimContext

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an academic literature search expert.
A researcher is writing a paper and needs to find citable references for a specific claim.
Your job is to generate 2-3 search queries that would find papers suitable as references
(i.e., papers the researcher should cite when making this claim).

Focus on finding:
- Original papers that introduced the concept, method, or finding mentioned in the claim
- Authoritative review papers or seminal works on the topic
- Papers that directly validate, benchmark, or formally describe what the claim states

Do NOT focus on papers that merely *use* or *apply* the concept in unrelated domains.
The goal is to find papers that a reviewer would expect to see cited for this claim.

IMPORTANT — Query construction strategy:
1. One query MUST target the original/seminal paper. If you can infer the official name,
   canonical title, or likely author names of the original work from the claim and context,
   include them. For example, if the claim mentions "CatBoost" as a method, search for
   the official paper title ("CatBoost unbiased boosting categorical features") or known
   authors, not just the claim's paraphrase of the method.
2. Another query should use the formal/technical terminology from the field, which may
   differ from how the claim phrases it (e.g., "oblivious decision trees" instead of
   "symmetric decision trees", "target leakage" instead of "overfitting").
3. Optionally, a third query targeting benchmark/comparison studies or authoritative reviews.

Tailor query angles based on the claim_type:
- background: original papers defining the concept, authoritative reviews
- method: methodology original paper, formal algorithm description, benchmark/comparison studies
- result: studies reporting the same metric/outcome on comparable populations
- interpretation: studies presenting the same or opposing interpretation, meta-analyses
- limitation: studies formally documenting the same limitation, proposed solutions

Return a JSON object: {"queries": ["query1", "query2", ...]}
Queries must be in English and suitable for academic search APIs.
Generate 2-3 queries. No more than 3."""

_USER_TEMPLATE = """\
Claim: "{claim_text}"

Context:
- Abstract: {abstract}
- Paragraph: {paragraph}
- Claim type: {claim_type}

Generate diverse search queries for this claim."""


async def generate_queries(
    claim_text: str,
    claim_context: ClaimContext,
    llm: LLMClient,
    cache: FileCache,
    model: str | None = None,
) -> list[str]:
    """Generate 2-3 search queries for the given claim.

    Returns an empty list on failure (caller should record an ExploreIssue).
    """
    cache_key = ("llm/query_generation", (claim_text, claim_context.claim_type.value))

    cached = cache.get(cache_key[0], cache_key[1])
    if cached is not None:
        queries: list[str] = cached if isinstance(cached, list) else cached.get("queries", [])
        logger.info("Query generation cache hit: %d queries", len(queries))
        return queries

    user_msg = _USER_TEMPLATE.format(
        claim_text=claim_text,
        abstract=claim_context.abstract,
        paragraph=claim_context.paragraph,
        claim_type=claim_context.claim_type.value,
    )

    try:
        result = await llm.complete_json(system=_SYSTEM_PROMPT, user=user_msg, model=model)
    except (LLMCallError, LLMParseError) as exc:
        logger.error("Query generation failed: %s", exc)
        return []

    queries = result.get("queries", []) if isinstance(result, dict) else []
    if not queries:
        logger.warning("LLM returned no queries")
        return []

    queries = queries[:3]

    cache.put(
        cache_key[0],
        cache_key[1],
        input_data={"claim_text": claim_text, "claim_type": claim_context.claim_type.value},
        output_data=queries,
    )

    logger.info("Generated %d queries: %s", len(queries), queries)
    return queries
