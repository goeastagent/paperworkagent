from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExtractLLMTaskSettings(BaseSettings):
    model: str = "gpt-5.2"
    temperature: float = 0.1
    timeout_seconds: int = 90


class ExtractLLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")

    provider: str = "openai"
    model: str = "gpt-5.2"
    api_key: str = ""

    claim_extract: ExtractLLMTaskSettings = Field(default_factory=ExtractLLMTaskSettings)


class CacheSettings(BaseSettings):
    enabled: bool = True
    directory: Path = Path(".cache/claim-extractor")


class ExtractSettings(BaseSettings):
    """Top-level settings for the Claim Extractor module."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm: ExtractLLMSettings = Field(default_factory=ExtractLLMSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    max_llm_calls: int = 3


def load_settings() -> ExtractSettings:
    """Load settings from environment and defaults."""
    settings = ExtractSettings()
    if not settings.llm.api_key:
        raise RuntimeError(
            "LLM_API_KEY is not set. "
            "Please set it in .env or as an environment variable."
        )
    if settings.llm.claim_extract.model == "gpt-5.2":
        settings.llm.claim_extract.model = settings.llm.model
    return settings
