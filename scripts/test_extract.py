"""Quick smoke test for the Claim Extractor pipeline.

Usage:
    python scripts/test_extract.py <fullpaper.md>
    python scripts/test_extract.py               # uses scripts/test_paper.md as default
"""

import asyncio
import logging
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paperworkagent.extract.config import load_settings
from paperworkagent.extract.extractor import extract_claims
from paperworkagent.extract.models import ExtractInput


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(fmt)
    root.addHandler(handler)

    for noisy in ("httpx", "httpcore", "litellm", "LiteLLM", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.CRITICAL)


def print_header(title: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def print_section(title: str) -> None:
    print(f"\n--- {title} ---")


async def main() -> None:
    setup_logging()

    paper_path = sys.argv[1] if len(sys.argv) > 1 else "../fullpaper.md"
    paper_file = Path(paper_path)

    if not paper_file.exists():
        print(f"Error: file not found: {paper_file}")
        sys.exit(1)

    print_header("Claim Extractor Smoke Test")

    settings = load_settings()
    print(f"  LLM model : {settings.llm.claim_extract.model}")
    print(f"  Timeout   : {settings.llm.claim_extract.timeout_seconds}s")
    print(f"  Paper     : {paper_file} ({paper_file.stat().st_size:,} bytes)")

    inp = ExtractInput(paper_path=str(paper_file))

    print("")
    result = await extract_claims(inp, settings)

    print_header("Results")
    print(f"  Status   : {result.status.value}")
    print(f"  Duration : {result.duration_seconds}s")

    if result.paper_title:
        print(f"  Title    : {result.paper_title}")

    if result.abstract:
        abstract_preview = result.abstract[:100] + "..." if len(result.abstract) > 100 else result.abstract
        print(f"  Abstract : {abstract_preview}")

    if result.issues:
        print_section(f"Issues ({len(result.issues)})")
        for iss in result.issues:
            print(f"  [{iss.type.value}] {iss.message}")
            if iss.detail:
                print(f"    detail: {iss.detail}")
    else:
        print(f"  Issues   : none")

    print_section(f"Claims ({len(result.claims)})")

    type_counts = Counter(c.claim_context.claim_type.value for c in result.claims)
    print(f"  Type distribution: {dict(type_counts)}")
    print()

    for i, claim in enumerate(result.claims, 1):
        ct = claim.claim_context.claim_type.value
        conf = claim.confidence
        section = claim.section_title
        text = claim.claim_text[:80]
        print(f"  {i:>2}. [{ct:14s}] (conf={conf:.2f}) [{section}]")
        print(f"      {text}{'...' if len(claim.claim_text) > 80 else ''}")
        print(f"      → {claim.reason}")
        print()

    out_path = Path(paper_file).with_suffix(".claims.json")
    out_path.write_text(
        result.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    print(f"  Full JSON output → {out_path}")
    print("")


if __name__ == "__main__":
    asyncio.run(main())
