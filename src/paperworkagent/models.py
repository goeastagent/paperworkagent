from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    BACKGROUND = "background"
    METHOD = "method"
    RESULT = "result"
    INTERPRETATION = "interpretation"
    LIMITATION = "limitation"


class SourceLocation(BaseModel):
    start_line: int
    end_line: int
    section: str


class Claim(BaseModel):
    claim_id: str
    section: str
    claim_text: str
    claim_type: ClaimType
    needs_reference: bool = True
    source_location: SourceLocation


class FactcheckLabel(str, Enum):
    SUPPORT = "support"
    PARTIAL = "partial"
    CONTRADICT = "contradict"
    UNRELATED = "unrelated"


class Paper(BaseModel):
    paper_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    doi: str | None = None
    pmid: str | None = None
    pmcid: str | None = None
    source_providers: list[str] = Field(default_factory=list)
    open_access_url: str | None = None
    fulltext: str | None = None


class Assessment(BaseModel):
    claim_id: str
    paper_id: str
    relevance_score: float = 0.0
    factcheck_label: FactcheckLabel = FactcheckLabel.UNRELATED
    confidence: float = 0.0
    rationale: str = ""
    evidence_spans: list[str] = Field(default_factory=list)


class Section(BaseModel):
    """A parsed section of the manuscript."""
    title: str
    level: int
    content: str
    start_line: int
    end_line: int
    paragraphs: list[str] = Field(default_factory=list)


class Manuscript(BaseModel):
    """Parsed manuscript structure."""
    sections: list[Section] = Field(default_factory=list)
    raw_text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResultsData(BaseModel):
    """Loaded results file summary."""
    filename: str
    columns: list[str] = Field(default_factory=list)
    row_count: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)
