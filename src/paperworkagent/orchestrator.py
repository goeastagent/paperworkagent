from __future__ import annotations

import asyncio
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from paperworkagent.assess.fact_checker import assess_claim_paper
from paperworkagent.config import Settings, load_settings
from paperworkagent.ingest.claim_extractor import extract_claims
from paperworkagent.ingest.markdown_parser import parse_markdown
from paperworkagent.infra.cache import Cache
from paperworkagent.llm.client import LLMClient
from paperworkagent.log import log
from paperworkagent.models import Assessment, Claim, Paper
from paperworkagent.retrieve import retrieve_for_claims
from paperworkagent.write.markdown_patcher import patch_markdown
from paperworkagent.write.report_writer import generate_report

STAGES = ("ingest", "retrieve", "assess", "write")


async def run_pipeline(
    manuscript_path: Path,
    results_dir: Path | None = None,
    output_dir: Path | None = None,
    from_stage: str | None = None,
    until_stage: str | None = None,
    settings: Settings | None = None,
) -> Path:
    settings = settings or load_settings()
    settings.llm.require_api_key()

    run_id = datetime.now().strftime("run-%Y%m%d-%H%M%S")
    out = output_dir or Path("runs") / run_id
    out.mkdir(parents=True, exist_ok=True)

    start_idx = 0
    if from_stage:
        if from_stage not in STAGES:
            raise ValueError(f"Unknown stage: {from_stage}. Must be one of {STAGES}")
        start_idx = STAGES.index(from_stage)

    end_idx = len(STAGES) - 1
    if until_stage:
        if until_stage not in STAGES:
            raise ValueError(f"Unknown stage: {until_stage}. Must be one of {STAGES}")
        end_idx = STAGES.index(until_stage)

    if start_idx > end_idx:
        raise ValueError(f"--from {from_stage} is after --until {until_stage}")

    cache = Cache(settings.cache.directory, enabled=settings.cache.enabled)
    llm = LLMClient(settings.llm, cache=cache)

    log.info(f"LLM: {settings.llm.provider}/{settings.llm.model}")
    log.info(f"output: {out}")
    stages_range = " → ".join(STAGES[start_idx:end_idx + 1])
    log.info(f"stages: {stages_range}")

    try:
        claims: list[Claim] = []
        papers: list[Paper] = []
        assessments: list[Assessment] = []

        # --- ingest ---
        if start_idx <= 0 and end_idx >= 0:
            log.stage_start("ingest")
            text = manuscript_path.read_text(encoding="utf-8")
            manuscript = parse_markdown(text)
            log.info(f"parsed {len(manuscript.sections)} sections from {manuscript_path.name}")
            claims = await extract_claims(manuscript, llm)
            _write_jsonl(out / "claims.jsonl", claims)
            log.stage_end("ingest", f"{len(claims)} claims extracted")
        elif end_idx >= 1:
            claims = _read_jsonl(out / "claims.jsonl", Claim)
            log.info(f"loaded {len(claims)} claims from existing claims.jsonl")

        if end_idx == 0:
            return out
        if not claims:
            raise RuntimeError("No claims extracted from manuscript.")

        ref_claims = [c for c in claims if c.needs_reference]
        skip_claims = len(claims) - len(ref_claims)
        if skip_claims > 0:
            log.info(f"filtering: {len(ref_claims)} claims need references, {skip_claims} skipped")

        # --- retrieve ---
        if start_idx <= 1 and end_idx >= 1:
            log.stage_start("retrieve")
            papers = await retrieve_for_claims(
                ref_claims,
                llm=llm,
                provider_names=settings.retrieval.providers,
                email=settings.openalex_email,
                cache=cache,
                max_results_per_claim=settings.retrieval.max_papers_per_claim,
            )
            _write_jsonl(out / "papers.jsonl", papers)
            log.stage_end("retrieve", f"{len(papers)} unique papers")
        elif end_idx >= 2:
            papers = _read_jsonl(out / "papers.jsonl", Paper)
            log.info(f"loaded {len(papers)} papers from existing papers.jsonl")

        if end_idx == 1:
            return out

        # --- assess ---
        if start_idx <= 2 and end_idx >= 2:
            log.stage_start("assess")
            assessments = await _assess_all(ref_claims, papers, llm)
            assessments.sort(key=lambda a: a.relevance_score, reverse=True)
            _write_jsonl(out / "assessments.jsonl", assessments)
            label_counts = _count_labels(assessments)
            log.stage_end("assess", f"{len(assessments)} assessments — {label_counts}")
        elif end_idx >= 3:
            assessments = _read_jsonl(out / "assessments.jsonl", Assessment)
            log.info(f"loaded {len(assessments)} assessments from existing assessments.jsonl")

        if end_idx == 2:
            return out

        # --- write ---
        if start_idx <= 3 and end_idx >= 3:
            log.stage_start("write")
            report = generate_report(claims, papers, assessments)  # all claims for context
            (out / "report.md").write_text(report, encoding="utf-8")
            log.info("report.md written")

            original_text = manuscript_path.read_text(encoding="utf-8")
            patched = patch_markdown(original_text, claims, papers, assessments)
            (out / "paper.with_refs.md").write_text(patched, encoding="utf-8")
            log.info("paper.with_refs.md written")
            log.stage_end("write", "all outputs generated")

    finally:
        cache.close()

    return out


async def _assess_all(
    claims: list[Claim],
    papers: list[Paper],
    llm: LLMClient,
    max_papers_per_claim: int = 10,
) -> list[Assessment]:
    assessments: list[Assessment] = []
    total_claims = len(claims)

    for ci, claim in enumerate(claims):
        ranked = _rank_papers_by_overlap(claim, papers)
        top_papers = ranked[:max_papers_per_claim]
        log.progress(ci, total_claims, f"assessing claim {claim.claim_id} against {len(top_papers)} papers")

        tasks = [assess_claim_paper(claim, paper, llm) for paper in top_papers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        ok = 0
        for result in results:
            if isinstance(result, Assessment):
                assessments.append(result)
                ok += 1

    log.progress(total_claims, total_claims, "assessment done")
    return assessments


def _rank_papers_by_overlap(claim: Claim, papers: list[Paper]) -> list[Paper]:
    claim_words = set(re.findall(r"[a-zA-Z]{3,}", claim.claim_text.lower()))
    scored: list[tuple[int, Paper]] = []
    for p in papers:
        text = f"{p.title} {p.abstract or ''}".lower()
        paper_words = set(re.findall(r"[a-zA-Z]{3,}", text))
        overlap = len(claim_words & paper_words)
        scored.append((overlap, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored]


def _count_labels(assessments: list[Assessment]) -> str:
    counts = Counter(a.factcheck_label.value for a in assessments)
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


def _write_jsonl(path: Path, items: list) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(item.model_dump_json() + "\n")


def _read_jsonl(path: Path, model_cls):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(model_cls.model_validate_json(line))
    return items
