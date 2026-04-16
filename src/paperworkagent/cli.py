"""Paperwork Agent CLI — entry point for all subcommands."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import typer

app = typer.Typer(name="paper-agent", help="논문 레퍼런스 에이전트")


@app.command()
def explore(
    claim: str = typer.Option(..., help="탐색 대상 주장 문장"),
    abstract: str = typer.Option(..., help="원본 논문의 초록"),
    paragraph: str = typer.Option(..., help="claim이 등장한 원문 문단"),
    claim_type: str = typer.Option(..., "--type", help="claim 유형: background, method, result, interpretation, limitation"),
    max_papers: int = typer.Option(10, "--max-papers", help="최종 반환할 최대 논문 수"),
    out: Path = typer.Option("exploration.json", "--out", help="출력 JSON 파일 경로"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="상세 로그 출력"),
) -> None:
    """단일 claim에 대해 관련 논문을 탐색한다."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    from paperworkagent.explore.config import load_settings
    from paperworkagent.explore.explorer import explore as run_explore
    from paperworkagent.explore.models import ClaimContext, ClaimType, ExploreInput

    try:
        ct = ClaimType(claim_type)
    except ValueError:
        typer.echo(f"Error: invalid claim type '{claim_type}'. "
                   f"Must be one of: {', '.join(t.value for t in ClaimType)}", err=True)
        raise typer.Exit(1)

    inp = ExploreInput(
        claim_text=claim,
        claim_context=ClaimContext(abstract=abstract, paragraph=paragraph, claim_type=ct),
        max_papers=max_papers,
    )

    try:
        settings = load_settings()
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    result = asyncio.run(run_explore(inp, settings))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        result.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    typer.echo(f"Status: {result.status.value}")
    typer.echo(f"Papers found: {len(result.papers)}")
    if result.issues:
        typer.echo(f"Issues: {len(result.issues)}")
        for issue in result.issues:
            typer.echo(f"  - [{issue.type.value}] {issue.message}")
    typer.echo(f"Summary: {result.summary}")
    typer.echo(f"Output written to {out}")


@app.command()
def extract(
    paper: Path = typer.Option(..., "--paper", help="Markdown 논문 초안 파일 경로"),
    out: Path = typer.Option("claims.json", "--out", help="출력 JSON 파일 경로"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="상세 로그 출력"),
) -> None:
    """논문 초안에서 reference가 필요한 claim을 추출한다."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    from paperworkagent.extract.config import load_settings
    from paperworkagent.extract.extractor import extract_claims as run_extract
    from paperworkagent.extract.models import ExtractInput

    try:
        settings = load_settings()
    except RuntimeError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1)

    inp = ExtractInput(paper_path=str(paper))
    result = asyncio.run(run_extract(inp, settings))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        result.model_dump_json(indent=2, exclude_none=True),
        encoding="utf-8",
    )
    typer.echo(f"Status: {result.status.value}")
    typer.echo(f"Claims extracted: {len(result.claims)}")
    if result.issues:
        typer.echo(f"Issues: {len(result.issues)}")
        for issue in result.issues:
            typer.echo(f"  - [{issue.type.value}] {issue.message}")
    if result.paper_title:
        typer.echo(f"Paper: {result.paper_title}")
    typer.echo(f"Duration: {result.duration_seconds}s")
    typer.echo(f"Output written to {out}")


if __name__ == "__main__":
    app()
