"""Shared test configuration.

Tests that call real LLM/provider APIs are marked with @pytest.mark.live.
Run them with: pytest -m live
Skip them with: pytest -m "not live"  (default)
"""

from __future__ import annotations

import pytest

from paperworkagent.config import LLMSettings, load_settings
from paperworkagent.infra.cache import Cache
from paperworkagent.llm.client import LLMClient


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False, help="Run live API tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: marks tests that call real APIs")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-live"):
        skip_live = pytest.mark.skip(reason="need --run-live to run")
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip_live)


@pytest.fixture
def llm_client() -> LLMClient:
    """Real LLM client from .env settings. Only usable in @pytest.mark.live tests."""
    settings = load_settings()
    settings.llm.require_api_key()
    cache = Cache(".cache/test", enabled=True)
    return LLMClient(settings.llm, cache=cache)
