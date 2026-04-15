import pytest
from pathlib import Path

from paperworkagent.ingest.claim_extractor import extract_claims
from paperworkagent.ingest.markdown_parser import parse_markdown
from paperworkagent.models import ClaimType

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_paper.md"


@pytest.mark.live
@pytest.mark.asyncio
async def test_extract_claims_produces_output(llm_client):
    text = FIXTURE.read_text()
    ms = parse_markdown(text)
    claims = await extract_claims(ms, llm_client)
    assert len(claims) > 0


@pytest.mark.live
@pytest.mark.asyncio
async def test_claims_have_required_fields(llm_client):
    text = FIXTURE.read_text()
    ms = parse_markdown(text)
    claims = await extract_claims(ms, llm_client)
    for c in claims:
        assert c.claim_id.startswith("c-")
        assert c.section
        assert c.claim_text
        assert c.claim_type in ClaimType


@pytest.mark.live
@pytest.mark.asyncio
async def test_entities_are_extracted(llm_client):
    text = FIXTURE.read_text()
    ms = parse_markdown(text)
    claims = await extract_claims(ms, llm_client)
    all_entities = []
    for c in claims:
        all_entities.extend(c.entities)
    assert any("BRCA1" in e for e in all_entities)
