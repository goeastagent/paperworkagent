from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

app = typer.Typer(name="paper-agent", help="논문 레퍼런스 에이전트 CLI")


def _make_llm():
    from paperworkagent.config import load_settings
    from paperworkagent.infra.cache import Cache
    from paperworkagent.llm.client import LLMClient

    settings = load_settings()
    settings.llm.require_api_key()
    cache = Cache(settings.cache.directory, enabled=settings.cache.enabled)
    llm = LLMClient(settings.llm, cache=cache)
    return settings, cache, llm


@app.command()
def run(
    manuscript: Path = typer.Option(..., "--manuscript", "-m", help="원고 Markdown 파일 경로"),
    results: Path | None = typer.Option(None, "--results", "-r", help="결과 파일 디렉터리"),
    out: Path | None = typer.Option(None, "--out", "-o", help="출력 디렉터리"),
    from_stage: str | None = typer.Option(None, "--from", help="재실행 시작 단계"),
    until_stage: str | None = typer.Option(None, "--until", help="이 단계까지만 실행"),
):
    """전체 파이프라인 실행 (--from, --until로 범위 지정 가능)."""
    if not manuscript.exists():
        typer.echo(f"Error: {manuscript} not found.", err=True)
        raise typer.Exit(1)

    from paperworkagent.orchestrator import run_pipeline

    output_dir = asyncio.run(
        run_pipeline(
            manuscript_path=manuscript,
            results_dir=results,
            output_dir=out,
            from_stage=from_stage,
            until_stage=until_stage,
        )
    )
    typer.echo(f"Done. Results written to {output_dir}/")


@app.command()
def ingest(
    manuscript: Path = typer.Option(..., "--manuscript", "-m", help="원고 Markdown 파일 경로"),
    out: Path | None = typer.Option(None, "--out", "-o", help="출력 디렉터리"),
):
    """ingest만 단독 실행: 원고 파싱 + claim 추출."""
    if not manuscript.exists():
        typer.echo(f"Error: {manuscript} not found.", err=True)
        raise typer.Exit(1)

    from paperworkagent.orchestrator import run_pipeline

    output_dir = asyncio.run(
        run_pipeline(
            manuscript_path=manuscript,
            output_dir=out,
            until_stage="ingest",
        )
    )
    typer.echo(f"Done. claims.jsonl written to {output_dir}/")


@app.command()
def search(
    query: str = typer.Option(..., "--query", "-q", help="검색어"),
    providers: str = typer.Option("openalex,crossref,europepmc", "--providers", "-p"),
    max_results: int = typer.Option(20, "--max-results"),
    out: Path = typer.Option("results.json", "--out", "-o"),
):
    """문헌 검색만 단독 실행."""
    from paperworkagent.models import Claim, ClaimType, SourceLocation
    from paperworkagent.retrieve import retrieve_for_claims

    settings, cache, llm = _make_llm()

    dummy_claim = Claim(
        claim_id="search-001",
        section="query",
        claim_text=query,
        claim_type=ClaimType.BACKGROUND,
        source_location=SourceLocation(start_line=0, end_line=0, section="query"),
    )

    provider_list = [p.strip() for p in providers.split(",")]
    papers = asyncio.run(
        retrieve_for_claims(
            [dummy_claim],
            llm=llm,
            provider_names=provider_list,
            email=settings.openalex_email,
            cache=cache,
            max_results_per_claim=max_results,
        )
    )
    cache.close()

    data = [p.model_dump() for p in papers]
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    typer.echo(f"Found {len(papers)} papers. Written to {out}")


@app.command(name="fact-check")
def fact_check(
    claim: str = typer.Option(..., "--claim", "-c", help="검증할 주장 텍스트"),
    paper_id: str = typer.Option(..., "--paper-id", help="대상 논문 DOI 또는 PMID"),
    out: Path = typer.Option("result.json", "--out", "-o"),
):
    """개별 주장 fact-check."""
    from paperworkagent.assess.fact_checker import assess_claim_paper
    from paperworkagent.models import Claim, ClaimType, Paper, SourceLocation
    from paperworkagent.retrieve import retrieve_for_claims

    settings, cache, llm = _make_llm()

    claim_obj = Claim(
        claim_id="fc-001",
        section="query",
        claim_text=claim,
        claim_type=ClaimType.RESULT,
        source_location=SourceLocation(start_line=0, end_line=0, section="query"),
    )

    papers = asyncio.run(
        retrieve_for_claims(
            [claim_obj],
            llm=llm,
            provider_names=["openalex", "crossref"],
            email=settings.openalex_email,
            cache=cache,
            max_results_per_claim=5,
        )
    )

    target = None
    for p in papers:
        if p.doi == paper_id or p.pmid == paper_id or p.paper_id == paper_id:
            target = p
            break

    if not target:
        target = Paper(paper_id=paper_id, title="", doi=paper_id if "/" in paper_id else None)

    result = asyncio.run(assess_claim_paper(claim_obj, target, llm))
    cache.close()

    out.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Label: {result.factcheck_label.value} | Confidence: {result.confidence:.0%}")
    typer.echo(f"Written to {out}")


if __name__ == "__main__":
    app()
