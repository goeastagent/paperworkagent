from __future__ import annotations

from paperworkagent.llm.client import LLMClient
from paperworkagent.models import Claim
from paperworkagent.retrieve.providers.base import SearchQuery

_SYSTEM = """You are a literature search query generator for biomedical databases.
Given a scientific claim, generate effective search terms.
Return a JSON object with exactly these fields:
- "keywords": list of 3-5 search keywords (English, specific, database-friendly)

Return ONLY a JSON object. No markdown fences, no explanation."""

_USER = """Generate search terms for this claim:

Claim: {claim_text}
Section: {section}
Type: {claim_type}"""


async def build_query(claim: Claim, llm: LLMClient, max_results: int = 20) -> SearchQuery:
    prompt = _USER.format(
        claim_text=claim.claim_text[:500],
        section=claim.section,
        claim_type=claim.claim_type.value,
    )
    result = await llm.complete_json(prompt, system=_SYSTEM)

    if not isinstance(result, dict):
        raise ValueError(f"LLM returned non-dict for query generation: {type(result)}")

    keywords = result.get("keywords", [])
    if not keywords:
        raise ValueError("LLM returned empty keywords for query generation")

    return SearchQuery(
        keywords=[str(k) for k in keywords[:5]],
        max_results=max_results,
    )
