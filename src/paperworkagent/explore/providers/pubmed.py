from __future__ import annotations

import logging
from typing import Any

import httpx

from paperworkagent.explore.models import PaperData
from paperworkagent.explore.providers.base import BaseProvider

logger = logging.getLogger(__name__)

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class PubMedProvider(BaseProvider):
    name = "pubmed"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=15)

    async def search(self, query: str, max_results: int = 20) -> list[PaperData]:
        pmids = await self._esearch(query, max_results)
        if not pmids:
            return []
        return await self._fetch_details(pmids)

    async def _esearch(self, query: str, max_results: int) -> list[str]:
        params: dict[str, Any] = {
            "db": "pubmed",
            "term": query,
            "retmax": min(max_results, 50),
            "retmode": "json",
            "sort": "relevance",
        }
        if self._api_key:
            params["api_key"] = self._api_key
        try:
            resp = await self._client.get(_ESEARCH_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("PubMed esearch failed for %r: %s", query, exc)
            return []

        id_list: list[str] = resp.json().get("esearchresult", {}).get("idlist") or []
        return id_list

    async def _fetch_details(self, pmids: list[str]) -> list[PaperData]:
        params: dict[str, Any] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        }
        if self._api_key:
            params["api_key"] = self._api_key
        try:
            resp = await self._client.get(_EFETCH_URL, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("PubMed efetch failed: %s", exc)
            return []

        return _parse_pubmed_xml(resp.text)

    async def close(self) -> None:
        await self._client.aclose()


def _parse_pubmed_xml(xml_text: str) -> list[PaperData]:
    """Minimal XML parsing without heavy dependencies."""
    import xml.etree.ElementTree as ET

    papers: list[PaperData] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("PubMed XML parse error")
        return []

    for article in root.iter("PubmedArticle"):
        try:
            medline = article.find("MedlineCitation")
            if medline is None:
                continue

            pmid_el = medline.find("PMID")
            pmid = pmid_el.text if pmid_el is not None else None

            art = medline.find("Article")
            if art is None:
                continue

            title_el = art.find("ArticleTitle")
            title = title_el.text if title_el is not None else None
            if not title:
                continue

            authors: list[str] = []
            author_list = art.find("AuthorList")
            if author_list is not None:
                for author in author_list.findall("Author"):
                    last = author.findtext("LastName", "")
                    fore = author.findtext("ForeName", "")
                    name = f"{last} {fore}".strip()
                    if name:
                        authors.append(name)

            abstract_el = art.find("Abstract")
            abstract: str | None = None
            if abstract_el is not None:
                parts = [t.text or "" for t in abstract_el.findall("AbstractText")]
                abstract = " ".join(parts).strip() or None

            year: int | None = None
            journal = art.find("Journal")
            if journal is not None:
                pub_date = journal.find("JournalIssue/PubDate")
                if pub_date is not None:
                    year_el = pub_date.find("Year")
                    if year_el is not None and year_el.text:
                        try:
                            year = int(year_el.text)
                        except ValueError:
                            pass

            venue: str | None = None
            if journal is not None:
                venue_el = journal.find("Title")
                if venue_el is not None:
                    venue = venue_el.text

            doi: str | None = None
            pmcid: str | None = None
            article_id_list = article.find("PubmedData/ArticleIdList")
            if article_id_list is not None:
                for aid in article_id_list.findall("ArticleId"):
                    id_type = aid.get("IdType", "")
                    if id_type == "doi" and aid.text:
                        doi = aid.text
                    elif id_type == "pmc" and aid.text:
                        pmcid = aid.text

            papers.append(PaperData(
                doi=doi,
                pmid=pmid,
                pmcid=pmcid,
                title=title,
                authors=authors,
                year=year,
                abstract=abstract,
                venue=venue,
                source_provider="pubmed",
            ))
        except Exception:
            continue

    return papers
