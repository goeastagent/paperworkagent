"""Claim Extractor: read paper → LLM call → structured claims."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from paperworkagent.common.cache import FileCache
from paperworkagent.common.llm import LLMClient, LLMCallError, LLMParseError
from paperworkagent.explore.models import ClaimContext, ClaimType
from paperworkagent.extract.config import ExtractSettings
from paperworkagent.extract.models import (
    MAX_CLAIMS,
    ExtractedClaim,
    ExtractInput,
    ExtractIssue,
    ExtractIssueType,
    ExtractOutput,
    ExtractStatus,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an academic writing assistant. Given a full paper draft in Markdown,
identify sentences that need scholarly references but currently have no citations.

Rules:
- Skip sentences in Abstract, Acknowledgments, and References sections
- Skip sentences that already have citations ([1], (Author et al., 2020), etc.)
- Skip sentences describing the authors' own new analysis, results, or methodology design
- Skip trivial/self-evident statements
- Identify sentences that state facts, mention tools/methods, compare with other studies,
  or reference prior work — these need references

Return a JSON object with:
- paper_title: the title of the paper
- abstract: the full abstract text from the paper
- claims: array of claim objects

For each claim, include:
- claim_text: the core claim for literature search (refined if needed)
- original_sentence: the verbatim original sentence
- section_title: which section it appears in
- paragraph: the full paragraph containing the sentence (verbatim, delimited by blank lines)
- claim_type: one of "background", "method", "result", "interpretation", "limitation"
- confidence: 0.0 to 1.0 (how certain that a reference is needed)
- reason: 1-2 sentence explanation in Korean for why a reference is needed

Return JSON: {"paper_title": "...", "abstract": "...", "claims": [...]}"""

_USER_TEMPLATE = "<paper>\n{paper_text}\n</paper>"

MAX_RETRIES = 2


async def extract_claims(inp: ExtractInput, settings: ExtractSettings) -> ExtractOutput:
    """Run the full extraction pipeline for a single paper."""
    start = time.monotonic()
    issues: list[ExtractIssue] = []

    paper_text = _read_paper(inp.paper_path)
    if paper_text is None:
        return _failed_output(
            issues=[ExtractIssue(
                type=ExtractIssueType.PARSE_FAILURE,
                message=f"파일을 읽을 수 없습니다: {inp.paper_path}",
            )],
            duration=time.monotonic() - start,
        )

    cache = FileCache(settings.cache.directory, enabled=settings.cache.enabled)
    model = settings.llm.claim_extract.model
    cache_key = ("llm", (paper_text, model))

    cached = cache.get(cache_key[0], cache_key[1])
    if cached is not None:
        logger.info("Cache hit for paper extraction")
        raw_response = cached
    else:
        llm = LLMClient(
            api_key=settings.llm.api_key,
            default_model=model,
            max_calls=settings.max_llm_calls,
            timeout=settings.llm.claim_extract.timeout_seconds,
        )
        raw_response = await _call_llm_with_retries(llm, paper_text, model, issues)
        if raw_response is None:
            return _failed_output(issues=issues, duration=time.monotonic() - start)

        cache.put(
            cache_key[0],
            cache_key[1],
            input_data={"paper_hash": "see_key", "model": model},
            output_data=raw_response,
        )

    paper_title, abstract, claims, parse_issues = _parse_response(raw_response)
    issues.extend(parse_issues)

    claims.sort(key=lambda c: c.confidence, reverse=True)
    claims = claims[:MAX_CLAIMS]

    status = ExtractStatus.SUCCESS if not issues else ExtractStatus.PARTIAL
    duration = time.monotonic() - start

    logger.info("Extraction complete: %d claims, status=%s (%.1fs)", len(claims), status.value, duration)

    return ExtractOutput(
        status=status,
        issues=issues,
        paper_title=paper_title,
        abstract=abstract,
        claims=claims,
        duration_seconds=round(duration, 2),
    )


def _read_paper(paper_path: str) -> str | None:
    """Read a Markdown file. Returns None on any failure."""
    path = Path(paper_path)
    if not path.exists():
        logger.error("File not found: %s", paper_path)
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.error("Failed to read file %s: %s", paper_path, exc)
        return None
    if not text.strip():
        logger.error("File is empty: %s", paper_path)
        return None
    return text


async def _call_llm_with_retries(
    llm: LLMClient,
    paper_text: str,
    model: str,
    issues: list[ExtractIssue],
) -> dict | None:
    """Call LLM with retry on parse failures. Returns parsed dict or None."""
    user_msg = _USER_TEMPLATE.format(paper_text=paper_text)

    for attempt in range(1 + MAX_RETRIES):
        try:
            result = await llm.complete_json(
                system=_SYSTEM_PROMPT,
                user=user_msg,
                model=model,
            )
            if isinstance(result, dict):
                return result
            logger.warning("LLM returned non-dict type: %s", type(result).__name__)
        except LLMCallError as exc:
            logger.error("LLM API call failed: %s", exc)
            issues.append(ExtractIssue(
                type=ExtractIssueType.LLM_FAILURE,
                message="LLM API 호출이 실패했습니다",
                detail=str(exc),
            ))
            return None
        except LLMParseError as exc:
            logger.warning("LLM parse failed (attempt %d/%d): %s", attempt + 1, 1 + MAX_RETRIES, exc)
            if attempt == MAX_RETRIES:
                issues.append(ExtractIssue(
                    type=ExtractIssueType.LLM_PARSE_FAILURE,
                    message=f"LLM JSON 파싱이 {1 + MAX_RETRIES}회 모두 실패했습니다",
                    detail=str(exc),
                ))
                return None

    return None


def _parse_response(
    raw: dict,
) -> tuple[str | None, str, list[ExtractedClaim], list[ExtractIssue]]:
    """Parse LLM response dict into structured output.

    Returns (paper_title, abstract, claims, issues).
    """
    issues: list[ExtractIssue] = []

    paper_title = raw.get("paper_title") or None
    abstract = raw.get("abstract") or ""
    raw_claims = raw.get("claims") or []

    if not isinstance(raw_claims, list):
        raw_claims = []

    claims: list[ExtractedClaim] = []
    invalid_count = 0

    for rc in raw_claims:
        if not isinstance(rc, dict):
            invalid_count += 1
            continue

        claim_text = rc.get("claim_text")
        raw_claim_type = rc.get("claim_type")

        if not claim_text or not raw_claim_type:
            invalid_count += 1
            continue

        claim_type = _parse_claim_type(str(raw_claim_type))

        original_sentence = rc.get("original_sentence") or claim_text
        section_title = rc.get("section_title") or "Unknown"
        paragraph = rc.get("paragraph") or original_sentence
        confidence = _parse_confidence(rc.get("confidence"))
        reason = rc.get("reason") or ""

        claims.append(ExtractedClaim(
            claim_text=str(claim_text),
            claim_context=ClaimContext(
                abstract=abstract,
                paragraph=str(paragraph),
                claim_type=claim_type,
            ),
            original_sentence=str(original_sentence),
            section_title=str(section_title),
            confidence=confidence,
            reason=str(reason),
        ))

    if invalid_count > 0:
        issues.append(ExtractIssue(
            type=ExtractIssueType.INVALID_CLAIMS,
            message=f"{invalid_count}개 claim이 필수 필드(claim_text, claim_type) 누락으로 무효 처리됨",
            detail=f"invalid_count={invalid_count}",
        ))

    return paper_title, abstract, claims, issues


def _parse_claim_type(raw: str) -> ClaimType:
    """Parse claim_type string with case-insensitive matching and fallback."""
    normalized = raw.strip().lower()
    for ct in ClaimType:
        if ct.value == normalized:
            return ct
    return ClaimType.BACKGROUND


def _parse_confidence(raw: object) -> float:
    """Parse confidence value with fallback to 0.5."""
    if raw is None:
        return 0.5
    try:
        val = float(raw)
        return max(0.0, min(1.0, val))
    except (ValueError, TypeError):
        return 0.5


def _failed_output(
    issues: list[ExtractIssue],
    duration: float,
) -> ExtractOutput:
    return ExtractOutput(
        status=ExtractStatus.FAILED,
        issues=issues,
        paper_title=None,
        abstract="",
        claims=[],
        duration_seconds=round(duration, 2),
    )
