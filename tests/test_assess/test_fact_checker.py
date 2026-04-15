import pytest

from paperworkagent.assess.fact_checker import assess_claim_paper
from paperworkagent.models import Claim, ClaimType, FactcheckLabel, Paper, SourceLocation


def _make_claim(text: str = "BRCA1 knockdown reduced cell viability in MDA-MB-231 cells.") -> Claim:
    return Claim(
        claim_id="c-001",
        section="results",
        claim_text=text,
        claim_type=ClaimType.RESULT,
        entities=["BRCA1", "MDA-MB-231"],
        methods=["knockdown"],
        outcomes=["reduced"],
        source_location=SourceLocation(start_line=1, end_line=1, section="results"),
    )


def _make_paper(abstract: str | None, title: str = "BRCA1 in breast cancer") -> Paper:
    return Paper(
        paper_id="doi:10.1234/test",
        title=title,
        authors=["Smith J"],
        year=2024,
        abstract=abstract,
        doi="10.1234/test",
    )


@pytest.mark.live
@pytest.mark.asyncio
async def test_assess_support(llm_client):
    claim = _make_claim()
    paper = _make_paper("BRCA1 knockdown reduced cell viability in MDA-MB-231 and other TNBC lines.")
    result = await assess_claim_paper(claim, paper, llm_client)
    assert result.claim_id == "c-001"
    assert result.factcheck_label in (FactcheckLabel.SUPPORT, FactcheckLabel.PARTIAL)
    assert result.relevance_score > 0.3
    assert result.rationale


@pytest.mark.live
@pytest.mark.asyncio
async def test_assess_unrelated(llm_client):
    claim = _make_claim()
    paper = _make_paper("Climate change impacts on agricultural yields in sub-Saharan Africa.", title="Climate and agriculture")
    result = await assess_claim_paper(claim, paper, llm_client)
    assert result.factcheck_label == FactcheckLabel.UNRELATED


@pytest.mark.asyncio
async def test_assess_no_abstract_returns_unrelated(llm_client=None):
    """No LLM needed — paper without abstract is auto-classified."""
    claim = _make_claim()
    paper = _make_paper(abstract=None)
    # fact_checker handles None abstract without calling LLM
    from paperworkagent.config import LLMSettings
    from paperworkagent.llm.client import LLMClient
    dummy_llm = LLMClient(LLMSettings(api_key="dummy"), cache=None)
    result = await assess_claim_paper(claim, paper, dummy_llm)
    assert result.factcheck_label == FactcheckLabel.UNRELATED
    assert result.confidence < 0.2
