from pathlib import Path

from paperworkagent.ingest.markdown_parser import normalize_section_name, parse_markdown

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_paper.md"


def test_parse_sections():
    text = FIXTURE.read_text()
    ms = parse_markdown(text)
    titles = [s.title for s in ms.sections]
    assert "Abstract" in titles
    assert "Methods" in titles
    assert "Results" in titles
    assert "Discussion" in titles


def test_section_has_paragraphs():
    text = FIXTURE.read_text()
    ms = parse_markdown(text)
    results = [s for s in ms.sections if s.title == "Results"][0]
    assert len(results.paragraphs) > 0
    assert "BRCA1" in results.content


def test_normalize_section_name():
    assert normalize_section_name("Materials and Methods") == "methods"
    assert normalize_section_name("3.1 Results") == "results"
    assert normalize_section_name("Discussion") == "discussion"
    assert normalize_section_name("Conclusions") == "discussion"
