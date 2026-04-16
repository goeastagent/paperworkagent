from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Relevance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRELATED = "unrelated"


class DiscoveryMethod(str, Enum):
    INITIAL_SEARCH = "initial_search"
    CITATION_BACKWARD = "citation_backward"
    CITATION_FORWARD = "citation_forward"
    RE_SEARCH = "re_search"


class ExploreStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ExploreIssueType(str, Enum):
    PROVIDER_FAILURE = "provider_failure"
    LLM_FAILURE = "llm_failure"
    LLM_PARSE_FAILURE = "llm_parse_failure"
    TIMEOUT = "timeout"
    NO_RESULTS = "no_results"


class ClaimType(str, Enum):
    BACKGROUND = "background"
    METHOD = "method"
    RESULT = "result"
    INTERPRETATION = "interpretation"
    LIMITATION = "limitation"


class ClaimContext(BaseModel):
    abstract: str
    paragraph: str
    claim_type: ClaimType


class ExploreInput(BaseModel):
    claim_text: str
    claim_context: ClaimContext
    seed_papers: list[str] = Field(default_factory=list)
    max_papers: int = 10


class PaperData(BaseModel):
    """In-memory paper record used during deduplication."""

    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    venue: str | None = None
    source_provider: str | None = None


class ExploredPaper(BaseModel):
    """Paper metadata + exploration metadata returned to caller."""

    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str | None = None
    venue: str | None = None
    relevance: Relevance
    relevance_reason: str
    discovery_method: DiscoveryMethod
    discovered_via: str | None = None


class SearchRound(BaseModel):
    round: int
    type: str
    queries: list[str] = Field(default_factory=list)
    papers_found: int
    papers_kept: int
    duration_seconds: float


class ExploreIssue(BaseModel):
    """A single issue encountered during exploration."""

    round: int
    type: ExploreIssueType
    message: str
    detail: str | None = None


class ExploreOutput(BaseModel):
    status: ExploreStatus
    issues: list[ExploreIssue] = Field(default_factory=list)
    papers: list[ExploredPaper]
    search_log: list[SearchRound]
    summary: str
