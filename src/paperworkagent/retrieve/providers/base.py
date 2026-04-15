from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SearchQuery:
    keywords: list[str] = field(default_factory=list)
    year_range: tuple[int, int] | None = None
    max_results: int = 20


@dataclass
class PaperResult:
    paper_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    source_provider: str = ""
    open_access_url: str | None = None
    cited_by_count: int | None = None


class BaseProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: SearchQuery) -> list[PaperResult]: ...

    @abstractmethod
    async def get_references(self, paper_id: str) -> list[str]: ...

    @abstractmethod
    async def get_cited_by(self, paper_id: str) -> list[str]: ...
