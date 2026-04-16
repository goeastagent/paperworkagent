from __future__ import annotations

import re
import unicodedata

from paperworkagent.explore.models import PaperData


def _normalize_doi(doi: str) -> str:
    return doi.lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/").strip()


def _normalize_title(title: str) -> str:
    text = title.lower()
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class PaperDeduplicator:
    """DOI / PMID / PMCID / normalized-title based in-memory deduplication."""

    def __init__(self) -> None:
        self._by_doi: dict[str, PaperData] = {}
        self._by_pmid: dict[str, PaperData] = {}
        self._by_pmcid: dict[str, PaperData] = {}
        self._by_title: dict[str, PaperData] = {}

    def add_or_merge(self, paper: PaperData) -> PaperData:
        existing = self._find_existing(paper)
        if existing is not None:
            self._merge_into(existing, paper)
            return existing
        self._index(paper)
        return paper

    @property
    def papers(self) -> list[PaperData]:
        seen_ids: set[int] = set()
        result: list[PaperData] = []
        for store in (self._by_doi, self._by_pmid, self._by_pmcid, self._by_title):
            for p in store.values():
                if id(p) not in seen_ids:
                    seen_ids.add(id(p))
                    result.append(p)
        return result

    def _find_existing(self, paper: PaperData) -> PaperData | None:
        if paper.doi:
            key = _normalize_doi(paper.doi)
            if key in self._by_doi:
                return self._by_doi[key]
        if paper.pmid and paper.pmid in self._by_pmid:
            return self._by_pmid[paper.pmid]
        if paper.pmcid and paper.pmcid in self._by_pmcid:
            return self._by_pmcid[paper.pmcid]
        norm = _normalize_title(paper.title)
        if norm and norm in self._by_title:
            return self._by_title[norm]
        return None

    def _index(self, paper: PaperData) -> None:
        if paper.doi:
            self._by_doi[_normalize_doi(paper.doi)] = paper
        if paper.pmid:
            self._by_pmid[paper.pmid] = paper
        if paper.pmcid:
            self._by_pmcid[paper.pmcid] = paper
        norm = _normalize_title(paper.title)
        if norm:
            self._by_title[norm] = paper

    @staticmethod
    def _merge_into(target: PaperData, source: PaperData) -> None:
        """Fill null fields in *target* from *source* (coalesce)."""
        if not target.doi and source.doi:
            target.doi = source.doi
        if not target.pmid and source.pmid:
            target.pmid = source.pmid
        if not target.pmcid and source.pmcid:
            target.pmcid = source.pmcid
        if not target.abstract and source.abstract:
            target.abstract = source.abstract
        if not target.venue and source.venue:
            target.venue = source.venue
        if not target.year and source.year:
            target.year = source.year
        if not target.authors and source.authors:
            target.authors = source.authors


def get_paper_identifier(paper: PaperData) -> str:
    """Return the best available identifier for cache key usage.

    Priority: DOI > PMID > PMCID > normalized title.
    """
    if paper.doi:
        return _normalize_doi(paper.doi)
    if paper.pmid:
        return paper.pmid
    if paper.pmcid:
        return paper.pmcid
    return _normalize_title(paper.title)
