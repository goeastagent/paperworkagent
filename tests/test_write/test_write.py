from paperworkagent.models import (
    Assessment, Claim, ClaimType, FactcheckLabel, Paper, SourceLocation,
)
from paperworkagent.write.citation_formatter import format_citation, format_citation_short
from paperworkagent.write.markdown_patcher import patch_markdown
from paperworkagent.write.report_writer import generate_report


def _sample_data():
    claim = Claim(
        claim_id="c-001",
        section="results",
        claim_text="BRCA1 knockdown reduced cell viability in MDA-MB-231 cells.",
        claim_type=ClaimType.RESULT,
        entities=["BRCA1", "MDA-MB-231"],
        methods=["knockdown"],
        outcomes=["reduced"],
        source_location=SourceLocation(start_line=10, end_line=10, section="results"),
    )
    paper = Paper(
        paper_id="10.1234/test",
        title="BRCA1 and Triple-Negative Breast Cancer",
        authors=["Smith J", "Lee K", "Park M"],
        year=2024,
        doi="10.1234/test",
        venue="Nature",
        abstract="BRCA1 knockdown reduced viability in TNBC.",
    )
    assessment = Assessment(
        claim_id="c-001",
        paper_id="10.1234/test",
        relevance_score=0.85,
        factcheck_label=FactcheckLabel.SUPPORT,
        confidence=0.78,
        rationale="효과 방향이 일치함.",
        evidence_spans=["BRCA1 knockdown reduced viability in TNBC."],
    )
    return [claim], [paper], [assessment]


def test_format_citation():
    paper = Paper(
        paper_id="10.1234/test",
        title="Test Paper Title",
        authors=["Smith J", "Lee K"],
        year=2024,
        doi="10.1234/test",
        venue="Nature",
    )
    citation = format_citation(paper)
    assert "Smith" in citation
    assert "2024" in citation
    assert "10.1234/test" in citation


def test_format_citation_short():
    paper = Paper(paper_id="x", title="T", authors=["Smith J", "Lee K"], year=2024)
    short = format_citation_short(paper)
    assert "Smith" in short
    assert "2024" in short


def test_generate_report():
    claims, papers, assessments = _sample_data()
    report = generate_report(claims, papers, assessments)
    assert "# 참고문헌 추천 보고서" in report
    assert "c-001" in report
    assert "지지" in report


def test_patch_markdown():
    claims, papers, assessments = _sample_data()
    original = "# Results\n\nBRCA1 knockdown reduced cell viability in MDA-MB-231 cells.\n"
    patched = patch_markdown(original, claims, papers, assessments)
    assert "REF_CANDIDATE" in patched
    assert "Suggested References" in patched
