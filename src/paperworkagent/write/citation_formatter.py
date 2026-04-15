from __future__ import annotations

from paperworkagent.models import Paper


def format_citation(paper: Paper) -> str:
    """Format a paper as a simple citation string."""
    parts: list[str] = []

    if paper.authors:
        if len(paper.authors) <= 3:
            parts.append(", ".join(paper.authors))
        else:
            parts.append(f"{paper.authors[0]} et al.")

    if paper.year:
        parts.append(f"({paper.year})")

    if paper.title:
        title = paper.title.rstrip(".")
        parts.append(f'"{title}."')

    if paper.venue:
        parts.append(f"*{paper.venue}*.")

    if paper.doi:
        parts.append(f"DOI: {paper.doi}")
    elif paper.pmid:
        parts.append(f"PMID: {paper.pmid}")

    return " ".join(parts)


def format_citation_short(paper: Paper) -> str:
    """Short inline citation like (Smith et al., 2024)."""
    author = paper.authors[0].split()[0] if paper.authors else "Unknown"
    suffix = " et al." if len(paper.authors) > 1 else ""
    year = paper.year or "n.d."
    return f"({author}{suffix}, {year})"
