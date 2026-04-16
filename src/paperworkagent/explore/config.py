from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMTaskSettings(BaseSettings):
    model: str = "gpt-5.2"
    temperature: float = 0.1
    timeout_seconds: int = 30


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")

    provider: str = "openai"
    model: str = "gpt-5.2"
    api_key: str = ""

    query_generation: LLMTaskSettings = Field(default_factory=LLMTaskSettings)
    relevance_filter: LLMTaskSettings = Field(default_factory=LLMTaskSettings)
    summary: LLMTaskSettings = Field(default_factory=LLMTaskSettings)


class ProviderSettings(BaseSettings):
    enabled: list[str] = Field(
        default=["openalex", "europepmc", "crossref", "semantic_scholar", "pubmed", "core"]
    )
    max_results_per_query: int = 20
    semaphore_limit: int = 3
    openalex_email: str = ""
    semantic_scholar_api_key: str = ""
    core_api_key: str = ""
    pubmed_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class CacheSettings(BaseSettings):
    enabled: bool = True
    directory: Path = Path(".cache/claim-explorer")


class ExploreSettings(BaseSettings):
    """Top-level settings for the Claim Explorer module."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm: LLMSettings = Field(default_factory=LLMSettings)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    batch_size: int = 10
    max_llm_calls: int = 100


def load_settings() -> ExploreSettings:
    """Load settings from environment and defaults."""
    settings = ExploreSettings()
    if not settings.llm.api_key:
        raise RuntimeError(
            "LLM_API_KEY is not set. "
            "Please set it in .env or as an environment variable."
        )
    for task in (settings.llm.query_generation, settings.llm.relevance_filter, settings.llm.summary):
        if task.model == "gpt-5.2":
            task.model = settings.llm.model
    return settings
