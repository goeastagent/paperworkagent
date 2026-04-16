from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from paperworkagent.explore.models import ClaimContext, ClaimType  # noqa: F401 (re-export for convenience)

MAX_CLAIMS: int = 50


class ExtractStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ExtractIssueType(str, Enum):
    PARSE_FAILURE = "parse_failure"
    LLM_FAILURE = "llm_failure"
    LLM_PARSE_FAILURE = "llm_parse_failure"
    INVALID_CLAIMS = "invalid_claims"


class ExtractInput(BaseModel):
    paper_path: str


class ExtractedClaim(BaseModel):
    claim_text: str
    claim_context: ClaimContext
    original_sentence: str
    section_title: str
    confidence: float
    reason: str


class ExtractIssue(BaseModel):
    type: ExtractIssueType
    message: str
    detail: str | None = None


class ExtractOutput(BaseModel):
    status: ExtractStatus
    issues: list[ExtractIssue] = Field(default_factory=list)
    paper_title: str | None = None
    abstract: str
    claims: list[ExtractedClaim]
    duration_seconds: float
