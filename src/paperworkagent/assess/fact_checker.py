from __future__ import annotations

from paperworkagent.llm.client import LLMClient
from paperworkagent.models import Assessment, Claim, FactcheckLabel, Paper

_SYSTEM = """You are a scientific fact-check assistant for biomedical research.
Given a claim from a manuscript and a candidate paper (title + abstract), assess their relationship.

Return a JSON object with exactly these fields:
- "label": one of "support", "partial", "contradict", "unrelated"
- "relevance_score": float 0.0-1.0 (how relevant is this paper to the claim)
- "confidence": float 0.0-1.0 (how confident are you in this assessment)
- "rationale": 1-2 sentence explanation in Korean
- "evidence_spans": list of 1-3 key sentences from the abstract that support your assessment

Return ONLY a JSON object. No markdown fences, no explanation."""

_USER = """Assess the relationship between this claim and paper:

## Claim
Section: {section}
Type: {claim_type}
Text: {claim_text}

## Paper
Title: {paper_title}
Year: {paper_year}
Abstract: {abstract}"""

_LABEL_MAP = {
    "support": FactcheckLabel.SUPPORT,
    "partial": FactcheckLabel.PARTIAL,
    "contradict": FactcheckLabel.CONTRADICT,
    "unrelated": FactcheckLabel.UNRELATED,
}


async def assess_claim_paper(
    claim: Claim,
    paper: Paper,
    llm: LLMClient,
) -> Assessment:
    """Produce a full Assessment for a claim-paper pair using LLM."""
    abstract = paper.abstract or paper.fulltext or ""
    if not abstract.strip():
        return Assessment(
            claim_id=claim.claim_id,
            paper_id=paper.paper_id,
            relevance_score=0.0,
            factcheck_label=FactcheckLabel.UNRELATED,
            confidence=0.1,
            rationale="초록 또는 본문이 없어 평가할 수 없음.",
        )

    prompt = _USER.format(
        section=claim.section,
        claim_type=claim.claim_type.value,
        claim_text=claim.claim_text[:500],
        paper_title=paper.title[:200],
        paper_year=paper.year or "unknown",
        abstract=abstract[:2000],
    )

    result = await llm.complete_json(prompt, system=_SYSTEM)

    if result is None or not isinstance(result, dict):
        return _fallback_assessment(claim, paper)

    label = _LABEL_MAP.get(result.get("label", ""), FactcheckLabel.UNRELATED)
    relevance = _clamp(result.get("relevance_score", 0.0))
    confidence = _clamp(result.get("confidence", 0.0))
    rationale = result.get("rationale", "")
    evidence_spans = result.get("evidence_spans", [])

    return Assessment(
        claim_id=claim.claim_id,
        paper_id=paper.paper_id,
        relevance_score=round(relevance, 3),
        factcheck_label=label,
        confidence=round(confidence, 3),
        rationale=rationale,
        evidence_spans=[str(s) for s in evidence_spans[:3]],
    )


def _fallback_assessment(claim: Claim, paper: Paper) -> Assessment:
    return Assessment(
        claim_id=claim.claim_id,
        paper_id=paper.paper_id,
        relevance_score=0.0,
        factcheck_label=FactcheckLabel.UNRELATED,
        confidence=0.1,
        rationale="LLM 응답 파싱 실패로 평가 불가.",
    )


def _clamp(v, lo: float = 0.0, hi: float = 1.0) -> float:
    try:
        return max(lo, min(float(v), hi))
    except (TypeError, ValueError):
        return 0.0
