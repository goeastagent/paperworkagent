"""Quick smoke test for the Claim Explorer pipeline.

Usage:
    python scripts/test_explore.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from paperworkagent.explore.config import load_settings
from paperworkagent.explore.explorer import explore
from paperworkagent.explore.models import ClaimContext, ClaimType, ExploreInput


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


CLAIM_TEXT = (
    "CatBoost employs ordered boosting and symmetric decision trees, "
    "offering robust handling of heterogeneous features with reduced overfitting."
)

ABSTRACT = (
    "This retrospective cohort study with external validation included 35,915 surgical cases "
    "from Seoul National University Hospital (2016-2019). Three CatBoost gradient boosting models "
    "were trained to predict packed red blood cell transfusion within 48 hours after surgery. "
    "The Combined model achieved an AUROC of 0.894 internally and 0.882 externally."
)

PARAGRAPH = (
    "All models were trained using the CatBoost gradient boosting classifier "
    "(CatBoostClassifier; iterations = 500, depth = 4, learning rate = 0.05). "
    "CatBoost was selected based on a comprehensive model comparison of 33 classifier "
    "configurations, in which it achieved the highest internal AUROC on the combined feature set. "
    "CatBoost employs ordered boosting and symmetric decision trees, offering robust handling "
    "of heterogeneous features with reduced overfitting."
)


def print_header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_section(title: str) -> None:
    print(f"\n--- {title} ---")


async def main() -> None:
    setup_logging()

    print_header("Claim Explorer Smoke Test")

    settings = load_settings()
    print(f"  LLM model   : {settings.llm.model}")
    print(f"  Providers    : {', '.join(settings.providers.enabled)}")
    print(f"  Batch size   : {settings.batch_size}")
    print(f"  Max papers   : 10")

    print_section("Input Claim")
    print(f"  Type : method")
    print(f"  Text : {CLAIM_TEXT[:80]}...")

    inp = ExploreInput(
        claim_text=CLAIM_TEXT,
        claim_context=ClaimContext(
            abstract=ABSTRACT,
            paragraph=PARAGRAPH,
            claim_type=ClaimType.METHOD,
        ),
        max_papers=10,
    )

    print("")
    result = await explore(inp, settings)

    print_header("Results")
    print(f"  Status : {result.status.value}")

    if result.issues:
        print_section(f"Issues ({len(result.issues)})")
        for iss in result.issues:
            print(f"  [{iss.type.value}] Round {iss.round}: {iss.message}")
    else:
        print(f"  Issues : none")

    print_section("Search Log")
    for rnd in result.search_log:
        print(f"  Round {rnd.round} ({rnd.type:20s})  "
              f"found={rnd.papers_found:>4d}  kept={rnd.papers_kept:>4d}  "
              f"time={rnd.duration_seconds:.1f}s")

    print_section(f"Papers ({len(result.papers)})")
    for i, paper in enumerate(result.papers, 1):
        rel = paper.relevance.value.upper()
        year = paper.year or "?"
        title = paper.title[:65]
        print(f"  {i:>2}. [{rel:6s}] ({year}) {title}")
        print(f"      {paper.relevance_reason}")

    print_section("Summary")
    print(f"  {result.summary}")

    out_path = Path("exploration_test.json")
    out_path.write_text(
        result.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    print(f"\n  Full JSON output → {out_path}")
    print("")


if __name__ == "__main__":
    asyncio.run(main())
