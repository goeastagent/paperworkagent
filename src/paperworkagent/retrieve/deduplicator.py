from __future__ import annotations

from paperworkagent.retrieve.providers.base import PaperResult


def deduplicate(papers: list[PaperResult]) -> list[PaperResult]:
    """Remove duplicate papers across providers using DOI/PMID/PMCID.

    When duplicates are found, merge source_provider info into one record,
    preferring the record with more metadata.
    """
    seen_doi: dict[str, int] = {}
    seen_pmid: dict[str, int] = {}
    unique: list[PaperResult] = []

    for paper in papers:
        doi_key = paper.doi.lower().strip() if paper.doi else None
        pmid_key = paper.pmid.strip() if paper.pmid else None

        existing_idx: int | None = None
        if doi_key and doi_key in seen_doi:
            existing_idx = seen_doi[doi_key]
        elif pmid_key and pmid_key in seen_pmid:
            existing_idx = seen_pmid[pmid_key]

        if existing_idx is not None:
            existing = unique[existing_idx]
            if paper.source_provider and paper.source_provider not in existing.source_provider:
                existing.source_provider += f",{paper.source_provider}"
            if not existing.abstract and paper.abstract:
                existing.abstract = paper.abstract
            if not existing.open_access_url and paper.open_access_url:
                existing.open_access_url = paper.open_access_url
            if not existing.pmid and paper.pmid:
                existing.pmid = paper.pmid
            if not existing.pmcid and paper.pmcid:
                existing.pmcid = paper.pmcid
        else:
            idx = len(unique)
            unique.append(paper)
            if doi_key:
                seen_doi[doi_key] = idx
            if pmid_key:
                seen_pmid[pmid_key] = idx

    return unique
