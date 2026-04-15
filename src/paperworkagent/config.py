from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    temperature: float = 0.1
    timeout_seconds: int = 30
    max_retries: int = 3

    def require_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "LLM API key is required. Set LLM_API_KEY in .env or config."
            )


class RetrievalSettings(BaseSettings):
    providers: list[str] = ["openalex", "crossref", "europepmc"]
    max_papers_per_claim: int = 20
    expand_citations: bool = True


class CacheSettings(BaseSettings):
    enabled: bool = True
    directory: str = ".cache"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    project_name: str = "paperworkagent"
    domain: str = "biomedical"

    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""
    openalex_email: str = ""

    llm: LLMSettings = Field(default_factory=LLMSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)

    def model_post_init(self, __context: Any) -> None:
        if self.llm_api_key and not self.llm.api_key:
            self.llm = LLMSettings(
                provider=self.llm_provider,
                model=self.llm_model,
                api_key=self.llm_api_key,
                temperature=self.llm.temperature,
                timeout_seconds=self.llm.timeout_seconds,
                max_retries=self.llm.max_retries,
            )

    @classmethod
    def from_yaml(cls, yaml_path: Path, env_file: Path | None = None) -> Settings:
        overrides: dict[str, Any] = {}
        if yaml_path.exists():
            with open(yaml_path) as f:
                raw = yaml.safe_load(f) or {}
            if "project" in raw:
                overrides["project_name"] = raw["project"].get("name", "paperworkagent")
                overrides["domain"] = raw["project"].get("domain", "biomedical")
            if "llm" in raw:
                overrides["llm"] = LLMSettings(**raw["llm"])
            if "retrieval" in raw:
                overrides["retrieval"] = RetrievalSettings(**raw["retrieval"])
            if "cache" in raw:
                overrides["cache"] = CacheSettings(**raw["cache"])
        return cls(**overrides)


def load_settings(project_dir: Path | None = None) -> Settings:
    base = project_dir or Path.cwd()
    yaml_path = base / "config" / "project.yaml"
    return Settings.from_yaml(yaml_path)
