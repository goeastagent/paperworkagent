from __future__ import annotations

from collections import defaultdict

from paperworkagent.models import Assessment, Claim, FactcheckLabel, Paper
from paperworkagent.write.citation_formatter import format_citation, format_citation_short


def patch_markdown(
    original_text: str,
    claims: list[Claim],
    papers: list[Paper],
    assessments: list[Assessment],
) -> str:
    """Insert REF_CANDIDATE annotations and a references section into the original markdown."""
    paper_map = {p.paper_id: p for p in papers}

    assessments_by_claim: dict[str, list[Assessment]] = defaultdict(list)
    for a in assessments:
        if a.factcheck_label in (FactcheckLabel.SUPPORT, FactcheckLabel.PARTIAL):
            assessments_by_claim[a.claim_id].append(a)

    for claim_id in assessments_by_claim:
        assessments_by_claim[claim_id].sort(key=lambda a: a.relevance_score, reverse=True)

    lines = original_text.splitlines()
    insertions: list[tuple[int, str]] = []

    for claim in claims:
        top_assessments = assessments_by_claim.get(claim.claim_id, [])[:3]
        if not top_assessments:
            continue

        claim_line = _find_claim_line(lines, claim.claim_text)
        if claim_line is None:
            continue

        for a in top_assessments:
            paper = paper_map.get(a.paper_id)
            if not paper:
                continue
            annotation = (
                f"<!-- [REF_CANDIDATE: {claim.claim_id} -> {a.paper_id} "
                f"| {a.factcheck_label.value} | confidence={a.confidence:.2f}] -->"
            )
            insertions.append((claim_line, annotation))

    for line_idx, annotation in sorted(insertions, key=lambda x: x[0], reverse=True):
        lines.insert(line_idx + 1, annotation)

    ref_section = _build_references_section(claims, papers, assessments_by_claim)
    if ref_section:
        lines.append("")
        lines.append(ref_section)

    return "\n".join(lines)


def _find_claim_line(lines: list[str], claim_text: str) -> int | None:
    """Find the line number containing the claim text (fuzzy match on first 50 chars)."""
    needle = claim_text[:50].strip()
    for i, line in enumerate(lines):
        if needle in line:
            return i
    return None


def _build_references_section(
    claims: list[Claim],
    papers: list[Paper],
    assessments_by_claim: dict[str, list[Assessment]],
) -> str:
    """Build a Suggested References section."""
    paper_map = {p.paper_id: p for p in papers}
    seen_papers: set[str] = set()
    ref_lines: list[str] = []
    ref_lines.append("## Suggested References\n")

    for claim in claims:
        top = assessments_by_claim.get(claim.claim_id, [])[:2]
        for a in top:
            if a.paper_id in seen_papers:
                continue
            seen_papers.add(a.paper_id)
            paper = paper_map.get(a.paper_id)
            if not paper:
                continue
            citation = format_citation(paper)
            ref_lines.append(f"- {citation}")

    if len(ref_lines) <= 1:
        return ""
    return "\n".join(ref_lines)
