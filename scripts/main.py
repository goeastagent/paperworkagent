"""Main pipeline: extract claims → explore references for each claim.

Usage:
    python scripts/main.py                                  # extract from fullpaper.md, then explore
    python scripts/main.py --claims fullpaper.claims.json   # skip extract, use existing claims
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paperworkagent.common.cache import FileCache
from paperworkagent.common.llm import LLMClient
from paperworkagent.explore.config import load_settings as load_explore_settings
from paperworkagent.explore.explorer import explore, _build_providers
from paperworkagent.explore.models import ExploreInput
from paperworkagent.extract.config import load_settings as load_extract_settings
from paperworkagent.extract.extractor import extract_claims
from paperworkagent.extract.models import ExtractedClaim, ExtractInput, ExtractOutput

CONCURRENCY = 3


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


async def run_extract(paper_path: str) -> ExtractOutput:
    settings = load_extract_settings()
    inp = ExtractInput(paper_path=paper_path)
    return await extract_claims(inp, settings)


async def run_explore_for_claim(
    idx: int,
    total: int,
    claim: ExtractedClaim,
    explore_settings,
    providers,
    cache: FileCache,
    semaphore: asyncio.Semaphore,
) -> dict:
    async with semaphore:
        label = f"[{idx}/{total}]"
        ct = claim.claim_context.claim_type.value
        print(f"\n  {label} [{ct}] (conf={claim.confidence:.2f}) "
              f"{claim.claim_text[:80]}{'...' if len(claim.claim_text) > 80 else ''}")

        llm = LLMClient(
            api_key=explore_settings.llm.api_key,
            default_model=explore_settings.llm.model,
            max_calls=explore_settings.max_llm_calls,
            timeout=explore_settings.llm.query_generation.timeout_seconds,
        )

        inp = ExploreInput(
            claim_text=claim.claim_text,
            claim_context=claim.claim_context,
            max_papers=10,
        )

        result = await explore(
            inp,
            explore_settings,
            providers=providers,
            llm=llm,
            cache=cache,
        )

        high = sum(1 for p in result.papers if p.relevance.value == "high")
        med = sum(1 for p in result.papers if p.relevance.value == "medium")
        print(f"  {label} → status={result.status.value}, "
              f"papers={len(result.papers)} (high={high}, med={med})")

        if result.papers:
            top = result.papers[0]
            print(f"  {label} → top: [{top.relevance.value}] "
                  f"({top.year or '?'}) {top.title[:65]}")

        return {
            "claim_text": claim.claim_text,
            "claim_type": ct,
            "section_title": claim.section_title,
            "confidence": claim.confidence,
            "reason": claim.reason,
            "explore_status": result.status.value,
            "explore_summary": result.summary,
            "papers": [p.model_dump(exclude_none=True) for p in result.papers],
        }


def parse_args() -> str | None:
    claims_path = None
    args = sys.argv[1:]
    if "--claims" in args:
        idx = args.index("--claims")
        if idx + 1 < len(args):
            claims_path = args[idx + 1]
    return claims_path


async def main() -> None:
    setup_logging()
    pipeline_start = time.monotonic()

    paper_path = "fullpaper.md"
    claims_path_arg = parse_args()

    # ── Step 1: Extract or load claims ──────────────────────────────────
    if claims_path_arg:
        print_header(f"Loading existing claims: {claims_path_arg}")
        raw = json.loads(Path(claims_path_arg).read_text(encoding="utf-8"))
        extract_result = ExtractOutput(**raw)
    else:
        print_header(f"Step 1: Extracting claims from {paper_path}")
        extract_result = await run_extract(paper_path)

        claims_out = Path(paper_path).with_suffix(".claims.json")
        claims_out.write_text(
            extract_result.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )
        print(f"  Claims saved to {claims_out}")

    if extract_result.status.value == "failed":
        print(f"\n  Extract failed. Aborting.")
        sys.exit(1)

    claims = extract_result.claims
    print(f"\n  Paper: {extract_result.paper_title}")
    print(f"  Claims: {len(claims)}")
    print(f"  Status: {extract_result.status.value}")

    # ── Step 2: Explore references ──────────────────────────────────────
    print_header(f"Step 2: Exploring references for {len(claims)} claims "
                 f"(concurrency={CONCURRENCY})")

    explore_settings = load_explore_settings()
    providers = _build_providers(explore_settings)
    cache = FileCache(explore_settings.cache.directory, enabled=explore_settings.cache.enabled)
    sem = asyncio.Semaphore(CONCURRENCY)

    try:
        tasks = [
            run_explore_for_claim(
                i, len(claims), claim,
                explore_settings, providers, cache, sem,
            )
            for i, claim in enumerate(claims, 1)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        for provider in providers:
            await provider.close()

    processed: list[dict] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            claim = claims[i]
            print(f"\n  [{i+1}/{len(claims)}] FAILED: {r}")
            processed.append({
                "claim_text": claim.claim_text,
                "claim_type": claim.claim_context.claim_type.value,
                "section_title": claim.section_title,
                "confidence": claim.confidence,
                "reason": claim.reason,
                "explore_status": "failed",
                "explore_summary": str(r),
                "papers": [],
            })
        else:
            processed.append(r)

    # ── Summary ─────────────────────────────────────────────────────────
    pipeline_duration = time.monotonic() - pipeline_start

    total_papers = sum(len(r["papers"]) for r in processed)
    successful = sum(1 for r in processed if r["explore_status"] != "failed")
    high_papers = sum(
        1 for r in processed
        for p in r["papers"]
        if p.get("relevance") == "high"
    )

    print_header("Pipeline Summary")
    print(f"  Total claims   : {len(claims)}")
    print(f"  Explored       : {successful}/{len(claims)}")
    print(f"  Total papers   : {total_papers}")
    print(f"  High relevance : {high_papers}")
    print(f"  Concurrency    : {CONCURRENCY}")
    print(f"  Duration       : {pipeline_duration:.1f}s")

    # ── Save combined output ────────────────────────────────────────────
    output = {
        "paper_title": extract_result.paper_title,
        "abstract": extract_result.abstract,
        "total_claims": len(claims),
        "total_papers_found": total_papers,
        "high_relevance_papers": high_papers,
        "duration_seconds": round(pipeline_duration, 2),
        "claims_with_references": processed,
    }

    out_path = Path(paper_path).with_suffix(".references.json")
    out_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n  Full output → {out_path}")
    print("")


if __name__ == "__main__":
    asyncio.run(main())
