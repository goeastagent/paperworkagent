from __future__ import annotations

from paperworkagent.ingest.markdown_parser import normalize_section_name
from paperworkagent.llm.client import LLMClient
from paperworkagent.log import log
from paperworkagent.models import Claim, ClaimType, Manuscript, SourceLocation

_TYPE_MAP = {
    "background": ClaimType.BACKGROUND,
    "method": ClaimType.METHOD,
    "result": ClaimType.RESULT,
    "interpretation": ClaimType.INTERPRETATION,
    "limitation": ClaimType.LIMITATION,
}

_SYSTEM = """You are a scientific claim extraction assistant for biomedical manuscripts.
Extract claims that NEED external literature references.

RULES:
1. DO NOT extract claims that merely describe THIS study's own procedures, data collection,
   sample selection, or specific numerical results. These don't need external references.
2. DO extract claims that assert something supportable or contradictable by other literature:
   background knowledge, methodological justifications, result interpretations, comparisons
   with prior work, generalizable conclusions.
3. MERGE related sub-claims into a single coherent claim.
4. Set "needs_reference" to false for this study's own unique observations.

Return a JSON array. Each object must have:
- "claim_text": the claim sentence
- "claim_type": one of background, method, result, interpretation, limitation
- "needs_reference": boolean

Return ONLY a JSON array."""

_USER = """Extract reference-worthy claims from this {section} section:

{text}"""


async def extract_claims(manuscript: Manuscript, llm: LLMClient) -> list[Claim]:
    all_claims: list[Claim] = []
    claim_counter = 0

    sections = [
        s for s in manuscript.sections
        if normalize_section_name(s.title) not in ("abstract",) and s.content.strip()
    ]

    for i, section in enumerate(sections):
        section_name = normalize_section_name(section.title)
        log.progress(i, len(sections), f"extracting claims from '{section.title}'")

        content = section.content[:4000].replace("\x00", "")
        prompt = _USER.format(section=section_name, text=content)
        result = await llm.complete_json(prompt, system=_SYSTEM)

        if result is None or not isinstance(result, list):
            log.info(f"  ⚠ skipping section '{section.title}'")
            continue

        for item in result:
            if not isinstance(item, dict) or "claim_text" not in item:
                continue

            claim_counter += 1
            claim_type = _TYPE_MAP.get(item.get("claim_type", ""), ClaimType.BACKGROUND)

            all_claims.append(
                Claim(
                    claim_id=f"c-{claim_counter:03d}",
                    section=section_name,
                    claim_text=item["claim_text"],
                    claim_type=claim_type,
                    needs_reference=bool(item.get("needs_reference", True)),
                    source_location=SourceLocation(
                        start_line=section.start_line,
                        end_line=section.end_line,
                        section=section_name,
                    ),
                )
            )

    log.progress(len(sections), len(sections), "claim extraction done")
    ref_needed = sum(1 for c in all_claims if c.needs_reference)
    log.info(f"  {len(all_claims)} claims, {ref_needed} need references, {len(all_claims) - ref_needed} skipped")
    return all_claims
