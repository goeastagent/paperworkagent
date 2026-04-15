from __future__ import annotations

from collections import defaultdict

from paperworkagent.models import Assessment, Claim, FactcheckLabel, Paper
from paperworkagent.write.citation_formatter import format_citation


def generate_report(
    claims: list[Claim],
    papers: list[Paper],
    assessments: list[Assessment],
) -> str:
    """Generate a human-readable report.md from assessment results."""
    paper_map = {p.paper_id: p for p in papers}
    claim_map = {c.claim_id: c for c in claims}
    assessments_by_claim: dict[str, list[Assessment]] = defaultdict(list)
    for a in assessments:
        assessments_by_claim[a.claim_id].append(a)

    lines: list[str] = []
    lines.append("# 참고문헌 추천 보고서\n")

    warnings: list[str] = []

    for claim in claims:
        claim_assessments = assessments_by_claim.get(claim.claim_id, [])
        claim_assessments.sort(key=lambda a: a.relevance_score, reverse=True)

        lines.append(f"## Claim {claim.claim_id}\n")
        lines.append(f"**섹션**: {claim.section} | **유형**: {claim.claim_type.value}\n")
        lines.append(f"> {claim.claim_text}\n")

        if not claim_assessments:
            lines.append("**추천 문헌 없음** — 검색 결과가 부족합니다.\n")
            warnings.append(f"- {claim.claim_id}: 관련 문헌을 찾지 못함")
            continue

        contradictions = [a for a in claim_assessments if a.factcheck_label == FactcheckLabel.CONTRADICT]
        if contradictions:
            warnings.append(f"- {claim.claim_id}: 반대 문헌 {len(contradictions)}건 발견")

        unsupported = all(
            a.factcheck_label in (FactcheckLabel.UNRELATED, FactcheckLabel.CONTRADICT)
            for a in claim_assessments
        )
        if unsupported:
            warnings.append(f"- {claim.claim_id}: 지지 문헌 없음")

        top = claim_assessments[:5]
        lines.append("| 순위 | 라벨 | 신뢰도 | 논문 |")
        lines.append("|------|------|--------|------|")
        for i, a in enumerate(top, 1):
            paper = paper_map.get(a.paper_id)
            if not paper:
                continue
            citation = format_citation(paper)
            label_str = _label_display(a.factcheck_label)
            lines.append(f"| {i} | {label_str} | {a.confidence:.0%} | {citation} |")
        lines.append("")

        best = top[0]
        if best.rationale:
            lines.append(f"**판정 근거**: {best.rationale}\n")
        if best.evidence_spans:
            lines.append("**근거 문장**:")
            for span in best.evidence_spans[:3]:
                lines.append(f'> "{span[:200]}"\n')

    if warnings:
        lines.append("---\n")
        lines.append("## 경고 사항\n")
        for w in warnings:
            lines.append(w)
        lines.append("")

    return "\n".join(lines)


def _label_display(label: FactcheckLabel) -> str:
    return {
        FactcheckLabel.SUPPORT: "지지",
        FactcheckLabel.PARTIAL: "부분 지지",
        FactcheckLabel.CONTRADICT: "반대",
        FactcheckLabel.UNRELATED: "무관",
    }.get(label, label.value)
